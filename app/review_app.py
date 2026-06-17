"""
FASHN Image Review App - Web interface for reviewing and approving generated images
Supports keyboard shortcuts and swipe gestures for quick review

IMPORTANT: On approval, if saleor_id is present, the image is automatically
uploaded to Saleor and the collection's backgroundImage is updated!
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import hashlib
import threading
from functools import wraps
from urllib.parse import urlparse, unquote
import requests as _http_requests
from PIL import Image
from flask import Flask, render_template, jsonify, request, Response, abort
from flask_cors import CORS
from core.generation_tracker import GenerationTracker
from core.prompt_manager import PromptManager
from core.s3_client import S3Client
from core.saleor_client import SaleorClient
from core.r2_client import R2Client
from core.fabric_analyzer import analyze_from_url
from core.flatlay_generator import get_onmodel_prompt
from core.imagen_generator import generate_flatlay as imagen_flatlay, generate_lifestyle as imagen_lifestyle, get_presets as imagen_presets

app = Flask(__name__)
CORS(app)

BASIC_AUTH_USER = os.getenv("BASIC_AUTH_USER")
BASIC_AUTH_PASS = os.getenv("BASIC_AUTH_PASS")


@app.before_request
def _require_basic_auth():
    if not BASIC_AUTH_USER or not BASIC_AUTH_PASS:
        return None
    if request.path == "/healthz":
        return None
    auth = request.authorization
    if auth and auth.username == BASIC_AUTH_USER and auth.password == BASIC_AUTH_PASS:
        return None
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Review App"'},
    )


@app.route('/healthz')
def _healthz():
    return ('ok', 200)


# Image proxy: fetch remote → resize → WebP → in-memory LRU cache.
# Cuts 10 MB 4K PNGs down to ~150 KB WebP. Browser sees one short, edge-cacheable response.
_ALLOWED_IMAGE_HOSTS = (
    "saleorme.s3.us-east-1.amazonaws.com",
    "saleorme.s3.amazonaws.com",
    "cdn.fashn.ai",
)
_IMG_CACHE_MAX = 256
_img_cache: dict[str, tuple[bytes, str]] = {}
_img_cache_order: list[str] = []
_img_cache_lock = threading.Lock()


def _img_cache_get(key: str):
    with _img_cache_lock:
        if key not in _img_cache:
            return None
        _img_cache_order.remove(key)
        _img_cache_order.append(key)
        return _img_cache[key]


def _img_cache_set(key: str, body: bytes, mime: str):
    with _img_cache_lock:
        if key in _img_cache:
            _img_cache_order.remove(key)
        _img_cache[key] = (body, mime)
        _img_cache_order.append(key)
        while len(_img_cache_order) > _IMG_CACHE_MAX:
            evict = _img_cache_order.pop(0)
            _img_cache.pop(evict, None)


@app.route('/img')
def img_proxy():
    raw_url = request.args.get('url', '')
    if not raw_url:
        abort(400, "missing url")
    url = unquote(raw_url)
    host = urlparse(url).hostname or ''
    if not (host in _ALLOWED_IMAGE_HOSTS
            or host.endswith('.r2.dev')
            or host.endswith('.amazonaws.com')):
        abort(403, f"host not allowed: {host}")

    try:
        width = int(request.args.get('w', '1080'))
    except ValueError:
        width = 1080
    width = max(64, min(width, 2400))
    quality = max(40, min(int(request.args.get('q', '80') or 80), 95))

    cache_key = hashlib.sha1(f"{url}|{width}|{quality}".encode()).hexdigest()
    hit = _img_cache_get(cache_key)
    if hit is not None:
        body, mime = hit
        resp = Response(body, mimetype=mime)
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        resp.headers['X-Cache'] = 'HIT'
        return resp

    try:
        r = _http_requests.get(url, timeout=20, stream=True)
        r.raise_for_status()
    except Exception as e:
        abort(502, f"fetch failed: {e}")

    try:
        src = Image.open(io.BytesIO(r.content))
        if src.mode in ('RGBA', 'LA'):
            bg = Image.new('RGB', src.size, (255, 255, 255))
            bg.paste(src, mask=src.split()[-1])
            src = bg
        elif src.mode != 'RGB':
            src = src.convert('RGB')
        if src.width > width:
            new_h = int(src.height * (width / src.width))
            src = src.resize((width, new_h), Image.LANCZOS)
        out = io.BytesIO()
        src.save(out, format='WEBP', quality=quality, method=6)
        body = out.getvalue()
    except Exception as e:
        abort(500, f"transform failed: {e}")

    _img_cache_set(cache_key, body, 'image/webp')
    resp = Response(body, mimetype='image/webp')
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    resp.headers['X-Cache'] = 'MISS'
    return resp


tracker = GenerationTracker()
prompt_manager = PromptManager()
s3_client = S3Client()
saleor_client = SaleorClient()
r2_client = R2Client()


@app.route('/')
def index():
    """Main review interface"""
    return render_template('review.html')


@app.route('/api/pending')
def get_pending():
    """Get all pending generations for review"""
    pending = tracker.get_pending_generations()
    return jsonify({
        "count": len(pending),
        "generations": pending
    })


@app.route('/api/generation/<generation_id>')
def get_generation(generation_id):
    """Get a specific generation"""
    gen = tracker.get_generation(generation_id)
    if gen:
        return jsonify(gen)
    return jsonify({"error": "Not found"}), 404


@app.route('/api/approve/<generation_id>', methods=['POST'])
def approve(generation_id):
    """
    Approve a generation

    If saleor_id is present:
    1. Move image to S3 approved folder
    2. Update Saleor collection with new background image
    """
    data = request.json or {}
    rating = data.get('rating', 5)
    notes = data.get('notes', '')

    gen = tracker.approve_generation(generation_id, rating=rating, notes=notes)
    if not gen:
        return jsonify({"error": "Not found"}), 404

    saleor_update_result = None
    saleor_error = None
    new_s3_url = None

    # Move to approved folder in S3
    if gen['output']['s3_url']:
        new_s3_url = s3_client.move_to_approved(gen['output']['s3_url'])
        if new_s3_url:
            # Persist the new location so future references don't 403 against the old path.
            gen['output']['s3_url'] = new_s3_url
            try:
                tracker._save_data()
            except Exception as e:
                print(f"[approve] save after S3 move failed: {e}")

    source_type = gen['source'].get('type')
    image_url = new_s3_url or gen['output'].get('s3_url') or gen['output'].get('fashn_url')

    if source_type == 'fabric' and image_url:
        # ── FABRIC APPROVE: Create product in Saleor ──
        try:
            fabric_code = gen['source'].get('id', 'unknown')
            folder_name = gen['source'].get('name', '').split('(')[-1].rstrip(')').strip() if '(' in gen['source'].get('name', '') else ''
            suit_style = gen.get('settings', {}).get('suit_style', 'slim-2pc')

            # Get color info from fabric analyzer
            fabric_url = gen['source'].get('image_url')
            color_name = "Premium Wool"
            if fabric_url:
                try:
                    color_info = analyze_from_url(fabric_url)
                    color_name = color_info.get('color_name', 'Premium Wool')
                except Exception:
                    pass

            print(f"[approve] Creating Saleor product: {fabric_code} ({color_name}) in {folder_name}")
            saleor_update_result = saleor_client.create_fabric_product(
                fabric_code=fabric_code,
                folder_name=folder_name,
                color_name=color_name,
                image_url=image_url,
                suit_style=suit_style,
                fabric_swatch_url=fabric_url,
            )
            print(f"[approve] Saleor product created! {saleor_update_result}")

        except Exception as e:
            saleor_error = str(e)
            print(f"[approve] Saleor error: {e}")

    elif source_type == 'collection':
        # ── COLLECTION APPROVE: Update background image ──
        saleor_id = gen['source'].get('saleor_id')
        if saleor_id and image_url:
            try:
                saleor_update_result = saleor_client.update_collection_background_image(
                    collection_id=saleor_id,
                    image_url=image_url,
                    alt_text=f"AI generated image for {gen['source']['name']}"
                )
            except Exception as e:
                saleor_error = str(e)

    elif source_type == 'product':
        # ── PRODUCT APPROVE: Append AI image to existing Saleor product (don't create new) ──
        saleor_id = gen['source'].get('saleor_id')
        if saleor_id and image_url:
            try:
                print(f"[approve] Adding image to Saleor product {saleor_id}: {image_url[:80]}")
                saleor_update_result = saleor_client.add_product_image(
                    product_id=saleor_id,
                    image_url=image_url,
                    alt_text=f"AI generated — {gen['source'].get('name','')}"
                )
                print(f"[approve] Saleor image added: {saleor_update_result}")
            except Exception as e:
                saleor_error = str(e)
                print(f"[approve] Saleor product image error: {e}")
        else:
            print(f"[approve] Skipped Saleor update — saleor_id={saleor_id} image_url={bool(image_url)}")

    # Record in prompt stats
    prompt_manager.record_generation(gen['prompt']['id'], approved=True)

    response = {
        "status": "approved",
        "generation": gen,
        "saleor_updated": saleor_update_result is not None,
        "saleor_result": saleor_update_result
    }

    if saleor_error:
        response["saleor_error"] = saleor_error

    return jsonify(response)


@app.route('/api/reject/<generation_id>', methods=['POST'])
def reject(generation_id):
    """Reject a generation"""
    data = request.json or {}
    reason = data.get('reason', 'Quality not acceptable')
    notes = data.get('notes', '')

    gen = tracker.reject_generation(generation_id, reason=reason, notes=notes)
    if gen:
        # Move to rejected folder in S3
        if gen['output']['s3_url']:
            s3_client.move_to_rejected(gen['output']['s3_url'])

        # Record in prompt stats
        prompt_manager.record_generation(gen['prompt']['id'], approved=False)

        return jsonify({"status": "rejected", "generation": gen})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/regenerate/<generation_id>', methods=['POST'])
def regenerate(generation_id):
    """Mark generation for regeneration"""
    gen = tracker.mark_for_regeneration(generation_id)
    if gen:
        return jsonify({"status": "regenerating", "generation": gen})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/statistics')
def get_statistics():
    """Get overall statistics"""
    gen_stats = tracker.get_statistics()
    prompt_stats = prompt_manager.get_statistics()
    learnings = prompt_manager.get_learnings()

    return jsonify({
        "generations": gen_stats,
        "prompts": prompt_stats,
        "learnings": learnings,
        "rejection_reasons": tracker.get_rejection_reasons()
    })


@app.route('/api/prompts')
def get_prompts():
    """Get all prompts"""
    return jsonify({
        "active": prompt_manager.get_active_prompt(),
        "all": prompt_manager.list_prompts()
    })


@app.route('/api/learning', methods=['POST'])
def add_learning():
    """Add a new learning"""
    data = request.json
    prompt_manager.add_learning(
        lesson=data.get('lesson'),
        severity=data.get('severity', 'info')
    )
    return jsonify({"status": "added"})


# ============================================================
# FABRIC SELECTOR ROUTES
# ============================================================

@app.route('/fabrics')
def fabric_selector():
    """Fabric selection interface for AI suit generation"""
    return render_template('fabric_selector.html')


@app.route('/api/fabric-folders')
def get_fabric_folders():
    """Get all fabric collection folders from R2"""
    folders = r2_client.list_fabric_folders()
    return jsonify({"folders": folders})


@app.route('/api/fabrics/<path:folder_path>')
def get_fabrics_in_folder(folder_path):
    """Get all fabric images in a specific folder"""
    if not folder_path.startswith('mtm-collection/'):
        folder_path = f"mtm-collection/{folder_path}/"
    if not folder_path.endswith('/'):
        folder_path += '/'
    fabrics = r2_client.list_fabrics_in_folder(folder_path)
    return jsonify({"fabrics": fabrics, "count": len(fabrics)})


@app.route('/api/generate-suits', methods=['POST'])
def generate_suits():
    """
    3-Stage Pipeline: Fabric Swatch -> Suit Image

    Stage 1: Analyze fabric color (RGB, HEX, name)
    Stage 2: Generate flat-lay suit with Recraft v3 (color-controlled) + color transfer
    Stage 3: FASHN product-to-model (flat-lay -> on-model)
    """
    import random
    from datetime import datetime
    from fashn import Fashn
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

    data = request.json or {}
    selected_fabrics = data.get('fabrics', [])
    suit_style = data.get('suit_style', 'slim-2pc')
    custom_prompt = data.get('custom_prompt', '')

    if not selected_fabrics:
        return jsonify({"error": "No fabrics selected"}), 400

    api_key = os.getenv("FASHN_API_KEY")
    if not api_key:
        return jsonify({"error": "FASHN_API_KEY not configured"}), 500

    fashn_client = Fashn(api_key=api_key)

    base_models = [
        {"name": "chang", "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/chang.jpeg"},
        {"name": "drick", "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/drick.jpeg"},
        {"name": "dutch-blond", "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/dutch-blond-model.jpeg"},
        {"name": "mark", "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/mark.jpeg"},
    ]

    results = []
    for fabric in selected_fabrics:
        fabric_url = fabric.get('url')
        fabric_code = fabric.get('code', 'unknown')
        fabric_folder = fabric.get('folder', '')
        selected_model = random.choice(base_models)

        # Create generation record
        generation = tracker.create_generation(
            source_type='fabric',
            source_id=fabric_code,
            source_name=f"Fabric {fabric_code} ({fabric_folder})",
            source_image_url=fabric_url,
            prompt_id=f"pipeline_{suit_style}",
            prompt_text=f"3-stage pipeline: {suit_style}",
            settings={"suit_style": suit_style, "pipeline": "3-stage"},
        )

        try:
            # ── STAGE 1: Analyze fabric color ──
            print(f"[{fabric_code}] Stage 1: Analyzing fabric color...")
            color_info = analyze_from_url(fabric_url)
            print(f"[{fabric_code}]   Color: {color_info['color_name']} ({color_info['hex']})")
            print(f"[{fabric_code}]   RGB: {color_info['rgb']}")

            # ── STAGE 2: FASHN product-to-model with color-aware prompt ──
            print(f"[{fabric_code}] Stage 2: FASHN product-to-model with color-aware prompt...")

            if custom_prompt:
                onmodel_prompt = custom_prompt
            else:
                style_desc = get_onmodel_prompt(suit_style)
                r, g, b = color_info['rgb']
                hex_color = color_info['hex']
                desc = color_info.get('description', '')
                onmodel_prompt = (
                    f"A fit male model wearing a {style_desc}. "
                    f"CRITICAL: The suit color MUST be EXACTLY {hex_color} (RGB {r},{g},{b}). "
                    f"This is a {desc} colored suit. "
                    f"The suit fabric must match the input swatch image precisely in color and texture. "
                    f"Do NOT make the suit gray or neutral - the color must be {hex_color}. "
                    f"Fine wool fabric. White dress shirt underneath. "
                    f"Professional fashion photography, clean studio background, "
                    f"full body visible, standing confidently, "
                    f"studio-quality lighting, high-end catalog quality."
                )

            fashn_result = fashn_client.predictions.subscribe(
                model_name="product-to-model",
                inputs={
                    "product_image": fabric_url,
                    "prompt": onmodel_prompt,
                    "aspect_ratio": "4:5",
                    "resolution": "4k",
                    "num_images": 1,
                    "output_format": "png",
                },
            )

            if fashn_result.status == "completed" and fashn_result.output:
                fashn_url = fashn_result.output[0] if isinstance(fashn_result.output, list) else fashn_result.output

                # Upload directly - no color transfer (was causing image corruption)
                s3_url = s3_client.upload_from_url(
                    image_url=fashn_url,
                    folder="fashn-api/new-collection-images",
                    filename=f"{fabric_code}_{suit_style}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )

                tracker.update_generation_output(
                    generation_id=generation['id'],
                    fashn_url=fashn_url,
                    s3_url=s3_url,
                    status="pending",
                    model_used=selected_model['name']
                )

                print(f"[{fabric_code}] DONE -> {s3_url}")
                results.append({
                    "fabric_code": fabric_code,
                    "status": "success",
                    "generation_id": generation['id'],
                    "color": color_info['hex'],
                    "color_name": color_info['color_name'],
                    "s3_url": s3_url,
                })
            else:
                raise Exception("FASHN product-to-model failed")

        except Exception as e:
            print(f"[{fabric_code}] ERROR: {e}")
            tracker.update_generation_output(
                generation_id=generation['id'],
                fashn_url=None, s3_url=None, status="failed"
            )
            results.append({"fabric_code": fabric_code, "status": "error", "error": str(e)})

    return jsonify({
        "total": len(selected_fabrics),
        "results": results,
        "successful": sum(1 for r in results if r['status'] == 'success'),
        "failed": sum(1 for r in results if r['status'] == 'error')
    })


def _build_suit_prompt(style: str, fabric_code: str) -> str:
    """Build AI prompt based on suit style selection"""
    base = (
        "A fit male model wearing a {style_desc}, "
        "professional fashion photography, clean studio background, "
        "full body visible, standing confidently, "
        "studio-quality lighting, perfect exposure, "
        "high-end catalog quality, sharp details"
    )

    styles = {
        "classic-2pc": "classic fit two-piece suit, single-breasted two-button jacket with notch lapel, "
                       "flat front straight leg trousers with plain hem, flap pockets, double side vents",
        "slim-2pc": "slim fit two-piece suit, single-breasted two-button jacket with notch lapel, "
                    "flat front slim tapered trousers with no break, flap pockets, single center vent",
        "modern-2pc-peak": "modern fit two-piece suit, single-breasted two-button jacket with peak lapel, "
                           "flat front straight leg trousers with plain hem, jetted pockets, double side vents",
        "slim-3pc": "slim fit three-piece suit with matching five-button V-neck waistcoat, "
                    "single-breasted two-button jacket with peak lapel, "
                    "flat front slim tapered trousers with no break",
        "classic-3pc": "classic fit three-piece suit with matching five-button V-neck waistcoat, "
                       "single-breasted two-button jacket with notch lapel, "
                       "flat front straight leg trousers with plain hem, double side vents",
        "db-6btn": "modern fit double-breasted six-button (2x3) suit, wide peak lapel, "
                   "flat front straight leg trousers with plain hem, jetted pockets",
        "db-4btn": "slim fit double-breasted four-button (2x2) suit, peak lapel, "
                   "flat front slim tapered trousers, jetted pockets",
        "tuxedo-shawl": "slim fit tuxedo, single-breasted one-button jacket with satin-faced shawl lapel, "
                        "satin covered buttons, jetted pockets, "
                        "flat front slim trousers with satin side stripe",
        "tuxedo-peak": "slim fit tuxedo, single-breasted one-button jacket with satin-faced peak lapel, "
                       "satin covered buttons, jetted pockets, "
                       "flat front slim trousers with satin side stripe",
        "3pc-db-vest": "modern fit three-piece suit with double-breasted peak lapel waistcoat, "
                       "single-breasted two-button jacket with peak lapel, "
                       "flat front straight leg trousers with plain hem",
        "3pc-shawl-vest": "slim fit three-piece suit with shawl collar waistcoat, "
                          "single-breasted two-button jacket with peak lapel, "
                          "flat front slim tapered trousers with no break",
    }

    if style == 'auto' or style not in styles:
        style = 'slim-2pc'

    return base.format(style_desc=styles[style])


# ============================================================
# IMAGEN 3 ROUTES
# ============================================================

@app.route('/api/analyze-color')
def analyze_color_endpoint():
    """Analyze fabric color from URL"""
    fabric_url = request.args.get('url')
    if not fabric_url:
        return jsonify({"error": "url parameter required"}), 400
    try:
        color_info = analyze_from_url(fabric_url)
        return jsonify(color_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/imagen/presets')
def get_imagen_presets():
    """Get available Imagen presets (models, scenes, styles)"""
    return jsonify(imagen_presets())


@app.route('/api/imagen/generate', methods=['POST'])
def imagen_generate():
    """
    Generate suit image with Imagen 3.
    Modes: 'flatlay' (product photo) or 'lifestyle' (editorial photo)
    """
    from datetime import datetime

    data = request.json or {}
    fabric_url = data.get('fabric_url')
    fabric_code = data.get('fabric_code', 'unknown')
    fabric_folder = data.get('fabric_folder', '')
    mode = data.get('mode', 'flatlay')  # flatlay or lifestyle
    suit_style = data.get('suit_style', 'slim-2pc')
    model_type = data.get('model_type', 'dutch-blond')
    scene_preset = data.get('scene_preset', 'classic-studio')
    custom_scene = data.get('custom_scene', '')
    color_name_override = data.get('color_name_override', '')

    if not fabric_url:
        return jsonify({"error": "fabric_url required"}), 400

    try:
        # Claude Vision AI analyzes the fabric color
        color_info = analyze_from_url(fabric_url)

        # Only override the name if user manually typed something different
        if color_name_override and color_name_override != color_info['color_name']:
            color_info['color_name'] = color_name_override

        print(f"[imagen] Color: {color_info['color_name']} ({color_info['hex']}) RGB{color_info['rgb']}")

        generation = tracker.create_generation(
            source_type='fabric',
            source_id=fabric_code,
            source_name=f"Fabric {fabric_code} ({fabric_folder})",
            source_image_url=fabric_url,
            prompt_id=f"imagen_{mode}_{suit_style}",
            prompt_text=f"Imagen 3 {mode}: {suit_style} / {model_type} / {scene_preset}",
            settings={"suit_style": suit_style, "pipeline": "imagen3", "mode": mode,
                       "model_type": model_type, "scene_preset": scene_preset},
        )

        if mode == 'flatlay':
            img_bytes = imagen_flatlay(color_info, suit_style)
            if not img_bytes:
                raise Exception("Imagen 3 flatlay generation failed")

            key = f"fashn-api/new-collection-images/{fabric_code}_imagen_{suit_style}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            s3_client.client.put_object(Bucket=s3_client.bucket_name, Key=key, Body=img_bytes, ContentType='image/png')
            s3_url = s3_client._get_public_url(key)

            tracker.update_generation_output(generation['id'], fashn_url=None, s3_url=s3_url, status="pending", model_used="imagen3")
            return jsonify({"status": "success", "fabric_code": fabric_code, "s3_url": s3_url,
                            "generation_id": generation['id'], "color": color_info['hex'], "color_name": color_info['color_name']})

        else:  # lifestyle
            images = imagen_lifestyle(color_info, suit_style, model_type, scene_preset, custom_scene)
            if not images:
                raise Exception("Imagen 3 lifestyle generation failed")

            urls = []
            for i, img_bytes in enumerate(images):
                key = f"fashn-api/new-collection-images/{fabric_code}_lifestyle_{scene_preset}_{i+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                s3_client.client.put_object(Bucket=s3_client.bucket_name, Key=key, Body=img_bytes, ContentType='image/png')
                urls.append(s3_client._get_public_url(key))

            # Save first image as the generation output
            tracker.update_generation_output(generation['id'], fashn_url=None, s3_url=urls[0], status="pending", model_used="imagen3")

            return jsonify({"status": "success", "fabric_code": fabric_code, "images": urls,
                            "generation_id": generation['id'], "color": color_info['hex'], "color_name": color_info['color_name'],
                            "count": len(urls)})

    except Exception as e:
        print(f"[imagen] ERROR: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# MTM CREATIVE FACTORY INTEGRATION
# Shows AI-approved factory products from the shared postgres ledger.
# Operator can reject retroactively -> unpublish + teach the reviewer.
# ============================================================
import json as _json
from contextlib import contextmanager as _contextmanager

import psycopg2 as _pg
import psycopg2.extras as _pg_extras

_FACTORY_PG = {
    "host": os.getenv("PGHOST", "91.98.235.81"),
    "port": int(os.getenv("PGPORT", "5433")),
    "dbname": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
}


@_contextmanager
def _factory_db():
    conn = _pg.connect(connect_timeout=8, **_FACTORY_PG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.route('/factory')
def factory_review():
    """Review interface for AI-approved MTM factory products."""
    return render_template('factory_review.html')


@app.route('/api/factory-pending')
def factory_pending():
    """AI-approved factory experiments that are live/published and not yet overridden."""
    with _factory_db() as c, c.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT experiment_key, fabric_code, fabric_book, concept, background,
                   image_r2_url, quality_score, review, saleor_product_id,
                   saleor_slug, landing_url, status, created_at
            FROM creative_experiments
            WHERE (review->>'approved') = 'true'
              AND status IN ('published','live','scaling','winner')
              AND override_reason IS NULL
            ORDER BY created_at DESC LIMIT 200
        """)
        rows = cur.fetchall()
    for r in rows:
        r["created_at"] = r["created_at"].isoformat() if r.get("created_at") else None
    return jsonify({"count": len(rows), "items": rows})


@app.route('/api/factory-reject/<path:experiment_key>', methods=['POST'])
def factory_reject(experiment_key):
    """Operator overrides an AI-approved product:
    1) mark experiment overridden (factory will stop ad + regenerate)
    2) save the reason as a reviewer learning (teaches the agent)
    3) unpublish the Saleor product (hide from storefront)."""
    data = request.json or {}
    reason = (data.get('reason') or 'operator rejected').strip()

    saleor_unpublished = False
    saleor_error = None
    with _factory_db() as c, c.cursor() as cur:
        cur.execute("SELECT saleor_product_id FROM creative_experiments "
                    "WHERE experiment_key=%s", (experiment_key,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "experiment not found"}), 404
        product_id = row[0]

        cur.execute("""UPDATE creative_experiments
            SET status='overridden', override_reason=%s, override_at=now(),
                updated_at=now(),
                decision_log = decision_log || %s::jsonb
            WHERE experiment_key=%s""",
            (reason, _json.dumps([{"action": "operator_override", "reason": reason}]),
             experiment_key))

        cur.execute("""INSERT INTO reviewer_learnings (lesson, severity, source)
            VALUES (%s, 'critical', %s)""", (reason, experiment_key))

    if product_id:
        try:
            saleor_client.unpublish_product(product_id)
            saleor_unpublished = True
        except Exception as e:
            saleor_error = str(e)

    return jsonify({"status": "overridden", "experiment_key": experiment_key,
                    "saleor_unpublished": saleor_unpublished,
                    "saleor_error": saleor_error,
                    "note": "ad will stop and the image will be regenerated; "
                            "the reviewer learned this lesson"})


@app.route('/api/factory-learning', methods=['POST'])
def factory_learning():
    """Add a free-form steering lesson for the reviewer without rejecting anything."""
    data = request.json or {}
    lesson = (data.get('lesson') or '').strip()
    if not lesson:
        return jsonify({"error": "lesson required"}), 400
    with _factory_db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO reviewer_learnings (lesson, severity, source) "
                    "VALUES (%s, %s, 'operator')",
                    (lesson, data.get('severity', 'info')))
    return jsonify({"status": "added", "lesson": lesson})


if __name__ == '__main__':
    print("=" * 60)
    print("FASHN Image Review App")
    print("=" * 60)
    print("\nOpen http://localhost:5000 in your browser")
    print("\nKeyboard shortcuts:")
    print("  → (Right Arrow) or A = Approve")
    print("  ← (Left Arrow) or R = Reject")
    print("  Space = Skip to next")
    print("  G = Regenerate")
    print("\n" + "-" * 60)
    print("SALEOR AUTO-UPDATE:")
    print("  Images with Saleor ID will automatically update")
    print("  the collection's backgroundImage in Saleor on approval!")
    print("=" * 60)

    app.run(debug=True, port=5000)
