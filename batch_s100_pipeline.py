"""
Batch S100 Pipeline — Fully automated fabric-to-product pipeline.
Picks 15 diverse fabrics from S100 collection, generates suit images,
creates Saleor products.

Per fabric generates 3 images:
  1. Lifestyle photo — 3-piece suit with waistcoat
  2. Studio white background — 3-piece suit with waistcoat
  3. Studio white background — 2-piece suit (no waistcoat)
  + fabric swatch as 4th image
"""

import sys
import os
import time
import json
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.r2_client import R2Client
from core.fabric_analyzer import analyze_from_url
from core.imagen_generator import generate_lifestyle, generate_flatlay
from core.s3_client import S3Client
from core.saleor_client import SaleorClient


# ── Config ──
COLLECTION_FOLDER = "new-1-super-100s"
R2_PREFIX = f"mtm-collection/{COLLECTION_FOLDER}/"
NUM_FABRICS = 15
DELAY_BETWEEN_IMAGEN = 15  # seconds between Imagen API calls (rate limit)
MAX_RETRIES = 3


def call_imagen_with_retry(func, *args, **kwargs):
    """Call Imagen with retry + exponential backoff for 429 errors."""
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                wait = DELAY_BETWEEN_IMAGEN * (attempt + 2)
                print(f"    ⏳ Rate limited, waiting {wait}s (retry {attempt+2}/{MAX_RETRIES})...")
                time.sleep(wait)
            else:
                raise

# Rotate model/scene for lifestyle shots
SCENE_ROTATION = [
    ("dutch-blond", "milan-street"),
    ("italian-dark", "evening-gala"),
    ("classic-british", "business-office"),
    ("young-modern", "hotel-lobby"),
    ("dutch-blond", "rooftop-sunset"),
    ("italian-dark", "autumn-city"),
    ("classic-british", "wedding-groom"),
    ("young-modern", "coastal-summer"),
    ("dutch-blond", "vintage-car"),
    ("italian-dark", "milan-street"),
    ("classic-british", "hotel-lobby"),
    ("young-modern", "business-office"),
    ("dutch-blond", "evening-gala"),
    ("italian-dark", "rooftop-sunset"),
    ("classic-british", "autumn-city"),
]


def pick_diverse_fabrics(fabrics: list, count: int) -> list:
    """Pick evenly spaced fabrics from the list for color diversity."""
    real_fabrics = [f for f in fabrics if f['code'].startswith('V')]
    if len(real_fabrics) <= count:
        return real_fabrics[:count]

    step = len(real_fabrics) / count
    selected = []
    for i in range(count):
        idx = int(i * step)
        selected.append(real_fabrics[idx])
    return selected


def upload_image(s3: S3Client, image_bytes: bytes, fabric_code: str, suffix: str) -> str:
    """Upload image bytes to S3, return public URL."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_key = f"fashn-api/product-images/{fabric_code}_{timestamp}_{suffix}.png"
    s3.client.put_object(
        Bucket=s3.bucket_name,
        Key=s3_key,
        Body=image_bytes,
        ContentType='image/png'
    )
    return f"https://{s3.bucket_name}.s3.{s3.region}.amazonaws.com/{s3_key}"


def run_batch():
    """Run the full batch pipeline."""
    print("=" * 70)
    print(f"  BATCH S100 PIPELINE — {NUM_FABRICS} fabrics × 3 images each")
    print(f"  Collection: {COLLECTION_FOLDER}")
    print(f"  Image plan: lifestyle(3pc) + studio(3pc) + studio(2pc) + swatch")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Initialize clients
    r2 = R2Client()
    s3 = S3Client()
    saleor = SaleorClient()

    # Get fresh Saleor token
    print("\n[1] Authenticating with Saleor...")
    saleor._get_fresh_token()
    print("  ✓ Saleor authenticated")

    # List fabrics
    print(f"\n[2] Loading fabrics from R2...")
    fabrics = r2.list_fabrics_in_folder(R2_PREFIX)
    print(f"  Found {len(fabrics)} fabrics total")

    # Skip fabrics already processed in earlier runs
    SKIP_CODES = set(os.environ.get("SKIP_FABRICS", "").split(",")) - {""}

    selected = pick_diverse_fabrics(fabrics, NUM_FABRICS)
    if SKIP_CODES:
        selected = [f for f in selected if f['code'] not in SKIP_CODES]
        print(f"  Skipping already processed: {SKIP_CODES}")

    print(f"  Selected {len(selected)} fabrics:")
    for f in selected:
        print(f"    - {f['code']}")

    # Process each fabric
    results = []

    print(f"\n[3] Processing {len(selected)} fabrics...\n")

    for i, fabric in enumerate(selected):
        fabric_code = fabric['code']
        fabric_url = fabric['url']
        model_type, scene = SCENE_ROTATION[i % len(SCENE_ROTATION)]

        print(f"{'─' * 60}")
        print(f"  [{i+1}/{len(selected)}] {fabric_code}")
        print(f"  Lifestyle: {model_type} / {scene}")

        try:
            # ── A: Color detection ──
            print(f"  → Claude Vision color analysis...")
            color_info = analyze_from_url(fabric_url)
            color_name = color_info['color_name']
            hex_color = color_info['hex']
            print(f"    Color: {color_name} ({hex_color})")

            # ── B: Image 1 — Lifestyle, 3-piece with waistcoat ──
            print(f"  → [1/3] Lifestyle 3-piece (Imagen 3)...")
            imgs_lifestyle = call_imagen_with_retry(
                generate_lifestyle,
                color_info=color_info,
                suit_style="slim-3pc",
                model_type=model_type,
                preset=scene,
                count=1,
            )
            url_lifestyle = upload_image(s3, imgs_lifestyle[0], fabric_code, "lifestyle_3pc")
            print(f"    ✓ Uploaded")

            time.sleep(DELAY_BETWEEN_IMAGEN)

            # ── C: Image 2 — Studio white bg, 3-piece ──
            print(f"  → [2/3] Studio 3-piece (Imagen 3)...")
            imgs_studio_3pc = call_imagen_with_retry(
                generate_lifestyle,
                color_info=color_info,
                suit_style="slim-3pc",
                model_type=model_type,
                preset="classic-studio",
                count=1,
            )
            url_studio_3pc = upload_image(s3, imgs_studio_3pc[0], fabric_code, "studio_3pc")
            print(f"    ✓ Uploaded")

            time.sleep(DELAY_BETWEEN_IMAGEN)

            # ── D: Image 3 — Studio white bg, 2-piece (no waistcoat) ──
            print(f"  → [3/3] Studio 2-piece (Imagen 3)...")
            imgs_studio_2pc = call_imagen_with_retry(
                generate_lifestyle,
                color_info=color_info,
                suit_style="slim-2pc",
                model_type=model_type,
                preset="classic-studio",
                count=1,
            )
            url_studio_2pc = upload_image(s3, imgs_studio_2pc[0], fabric_code, "studio_2pc")
            print(f"    ✓ Uploaded")

            # ── E: Create Saleor product ──
            print(f"  → Creating Saleor product...")
            product_result = saleor.create_fabric_product(
                fabric_code=fabric_code,
                folder_name=COLLECTION_FOLDER,
                color_name=color_name,
                image_url=url_lifestyle,
                suit_style="slim-3pc",
                extra_images=[url_studio_3pc, url_studio_2pc],
                fabric_swatch_url=fabric_url,
            )

            results.append({
                "fabric_code": fabric_code,
                "color_name": color_name,
                "hex": hex_color,
                "model_type": model_type,
                "scene": scene,
                "images": {
                    "lifestyle_3pc": url_lifestyle,
                    "studio_3pc": url_studio_3pc,
                    "studio_2pc": url_studio_2pc,
                    "swatch": fabric_url,
                },
                "product_id": product_result["product_id"],
                "status": "success",
            })

            print(f"  ✓ DONE — {color_name} ({hex_color}) → 4 images → Saleor ✓")

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({
                "fabric_code": fabric_code,
                "status": "error",
                "error": str(e),
            })

        # Pause between fabrics
        if i < len(selected) - 1:
            print(f"  (waiting 3s...)")
            time.sleep(3)

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print(f"  BATCH COMPLETE — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'=' * 70}")

    success = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']

    print(f"\n  ✓ Success: {len(success)}/{len(selected)}")
    print(f"  ✗ Failed:  {len(failed)}/{len(selected)}")

    if success:
        imagen_cost = len(success) * 3 * 0.04  # 3 Imagen calls per fabric
        vision_cost = len(success) * 0.01
        total = imagen_cost + vision_cost
        print(f"\n  Cost: ~${imagen_cost:.2f} (Imagen) + ~${vision_cost:.2f} (Vision) = ~${total:.2f}")
        print(f"\n  Products:")
        for r in success:
            print(f"    {r['fabric_code']}: {r['color_name']} ({r['hex']}) — {r['model_type']}/{r['scene']}")

    if failed:
        print(f"\n  Failed:")
        for r in failed:
            print(f"    {r['fabric_code']}: {r.get('error', '?')[:80]}")

    # Save results
    output_file = f"output/batch_s100_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("output", exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            "collection": COLLECTION_FOLDER,
            "finished": datetime.now().isoformat(),
            "total": len(selected),
            "success": len(success),
            "failed": len(failed),
            "images_per_product": "lifestyle_3pc + studio_3pc + studio_2pc + swatch",
            "results": results,
        }, f, indent=2)

    print(f"\n  Results: {output_file}")
    print(f"  Products LIVE on pomandi.com!")
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            NUM_FABRICS = int(sys.argv[1])
        except ValueError:
            pass
    run_batch()
