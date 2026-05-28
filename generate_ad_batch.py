"""
Reklam görseli batch generator
- 10 Saleor ürünü → 10 farklı sahne → FASHN product-to-model
- generations.json'a 'pending' olarak yazar
- Review app /api/pending'de gözükür
"""
import os, sys, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from fashn import Fashn
from core.generation_tracker import GenerationTracker
from core.s3_client import S3Client

load_dotenv()
fashn = Fashn(api_key=os.getenv("FASHN_API_KEY"))
tracker = GenerationTracker()
s3 = S3Client()

# 10 belirgin sahne — her ürüne 1 tane
SCENES = [
    ("milan-street",     "walking through Milan Fashion District at golden hour, soft out-of-focus storefronts behind, warm afternoon light, high-end editorial photography"),
    ("wedding-groom",    "elegant wedding venue, soft natural light from a tall window, romantic blurred floral arrangements, full body, refined editorial photography"),
    ("business-office",  "modern executive boardroom, large city-skyline window behind, soft daylight, confident posture, business editorial photography"),
    ("evening-gala",     "luxurious evening gala interior, warm chandelier glow, polished marble floor, blurred crystal lighting bokeh, full body, fashion editorial"),
    ("hotel-lobby",      "grand luxury hotel lobby, ornate marble columns, golden warm lighting, soft bokeh, full body, refined fashion editorial"),
    ("rooftop-sunset",   "city rooftop at sunset, warm orange-pink sky, blurred skyline, cinematic light, full body, modern fashion editorial"),
    ("autumn-city",      "European cobblestone street in autumn, warm golden leaves, soft overcast light, full body, fashion editorial photography"),
    ("vintage-car",      "leaning against a vintage 1960s European car on a quiet street, golden hour, blurred period background, cinematic, full body, editorial photography"),
    ("coastal-summer",   "Mediterranean coastal promenade, soft turquoise sea blurred behind, warm summer light, full body, fashion editorial"),
    ("classic-studio",   "minimal studio with seamless warm beige backdrop, soft top key light with subtle shadow, full body, high-end catalog photography"),
]

def build_prompt(scene_desc):
    return (
        f"Tall confident male model wearing the suit from the source image. "
        f"{scene_desc}. "
        f"Sharp symmetrical features, clean-shaven, healthy skin, relaxed yet confident pose. "
        f"4:5 aspect ratio, full body visible from head to shoes, "
        f"professional fashion editorial photography, perfect exposure, sharp details. "
        f"Do NOT change the suit color, fabric pattern, or cut — match exactly."
    )

with open('/tmp/picks.json') as f:
    picks = json.load(f)

print(f"=== {len(picks)} ürün × 1 sahne — toplam {len(picks)} reklam görseli üretiliyor ===\n")

results = []
for i, prod in enumerate(picks):
    scene_id, scene_desc = SCENES[i]
    media = prod.get('media') or []
    if not media:
        print(f"[{i+1}/{len(picks)}] {prod['name'][:40]} — media yok, atlanıyor"); continue
    img_url = media[0]['url']

    print(f"[{i+1}/{len(picks)}] {prod['name'][:50]}  →  scene: {scene_id}")

    # Pending generation kaydı
    gen = tracker.create_generation(
        source_type='product',
        source_id=prod['id'],
        source_name=prod['name'],
        source_image_url=img_url,
        prompt_id=f"ad_v1_{scene_id}",
        prompt_text=build_prompt(scene_desc),
        settings={"aspect_ratio": "4:5", "resolution": "4k", "scene": scene_id, "purpose": "ad_creative"},
        saleor_id=prod['id'],
        channel='belgium-channel',
    )

    try:
        res = fashn.predictions.subscribe(
            model_name="product-to-model",
            inputs={
                "product_image": img_url,
                "prompt": build_prompt(scene_desc),
                "aspect_ratio": "4:5",
                "resolution": "4k",
                "num_images": 1,
                "output_format": "png",
            },
        )
        if res.status == "completed" and res.output:
            fashn_url = res.output[0] if isinstance(res.output, list) else res.output
            slug = prod.get('slug','prod')[:30]
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_url = s3.upload_from_url(
                image_url=fashn_url,
                folder="fashn-api/new-collection-images",
                filename=f"AD_{slug}_{scene_id}_{ts}.png"
            )
            tracker.update_generation_output(
                generation_id=gen['id'],
                fashn_url=fashn_url, s3_url=s3_url,
                status="pending", model_used=f"fashn_{scene_id}",
            )
            print(f"     ✓ {s3_url}")
            results.append({"product": prod['name'], "scene": scene_id, "s3_url": s3_url, "ok": True})
        else:
            raise Exception(f"FASHN status={res.status}")
    except Exception as e:
        tracker.update_generation_output(generation_id=gen['id'], fashn_url=None, s3_url=None, status="failed")
        print(f"     ✗ HATA: {e}")
        results.append({"product": prod['name'], "scene": scene_id, "ok": False, "error": str(e)})
    time.sleep(2)

ok = sum(1 for r in results if r.get('ok'))
print(f"\n=== Sonuç: {ok}/{len(results)} başarılı ===")
with open('data/ad_batch_result.json','w') as f:
    json.dump({"timestamp": datetime.now().isoformat(), "results": results}, f, indent=2)
print("Sonuçlar: data/ad_batch_result.json")
print("\nReview app: python cli.py review  →  http://localhost:5000")
