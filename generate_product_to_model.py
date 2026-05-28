"""
Generate collection images using FASHN Product-to-Model API
This is the correct endpoint for professional product photography
"""

import os
import time
from dotenv import load_dotenv
from fashn import Fashn
from s3_uploader import upload_generated_image

load_dotenv()

# Configuration
FASHN_API_KEY = os.getenv("FASHN_API_KEY")

# Base model for face reference (optional)
BASE_MODEL_URL = "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/dutch-blond-model.jpeg"

# Collection garment images from S3
COLLECTION_GARMENTS = {
    "tuxedo": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-09-04_at_09.17.59_616cab49_thumbnail_4096.jpeg",
    "black-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.54_59449144_thumbnail_4096.jpeg",
    "blue-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.25_9dce9985_thumbnail_4096.jpeg",
    "burgundy-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.52_e35422ce_thumbnail_4096.jpeg",
    "beige-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/Beige_trouwpak_5_a70a4b44_thumbnail_4096.jpeg",
    "gray-wedding-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.05_8fc1e4dc_thumbnail_4096.jpeg",
    "green-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.28.03_0d1d3798_thumbnail_4096.jpeg",
}

# Professional styling prompt
# NOTE: Avoid brand names like "Vogue" as they may appear as watermarks
STYLING_PROMPT = """
Tall elegant blond Dutch man, age 28-32, refined Italian style tailoring,
standing confidently with full body visible. Sharp symmetrical features,
clean-shaven, healthy glowing skin. Relaxed yet confident pose.
Soft out-of-focus Italian city street background inspired by Milan fashion district,
warm natural daylight, gentle shadows. Studio-quality lighting, perfect exposure,
professional fashion editorial photography, high-end catalog quality.
"""


def generate_product_to_model(
    product_image_url: str,
    collection_slug: str,
    use_face_reference: bool = True,
    resolution: str = "4k"
) -> dict:
    """
    Generate image using Product-to-Model endpoint

    Args:
        product_image_url: URL of the product/garment image
        collection_slug: Collection name for file naming
        use_face_reference: Whether to use face reference image
        resolution: '1k' for catalog, '4k' for high-def renders

    Returns:
        dict with status and URLs
    """
    client = Fashn(api_key=FASHN_API_KEY)

    print(f"\n{'='*60}")
    print(f"Product-to-Model: {collection_slug}")
    print(f"{'='*60}")
    print(f"  Product: {product_image_url[:60]}...")
    print(f"  Resolution: {resolution}")
    print(f"  Face Reference: {use_face_reference}")
    print()

    # Build inputs
    inputs = {
        "product_image": product_image_url,
        "prompt": STYLING_PROMPT.strip().replace('\n', ' '),
        "aspect_ratio": "4:5",  # Optimal for mobile, Meta Ads, website
        "resolution": resolution,
        "num_images": 1,
        "output_format": "png",
    }

    # Add face reference for consistent look
    if use_face_reference:
        inputs["face_reference"] = BASE_MODEL_URL
        inputs["face_reference_mode"] = "match_reference"

    try:
        result = client.predictions.subscribe(
            model_name="product-to-model",
            inputs=inputs,
            on_enqueued=lambda pid: print(f"  Queued: {pid}"),
            on_queue_update=lambda status: print(f"  Status: {status.status}"),
        )

        print()

        if result.status == "completed" and result.output:
            fashn_url = result.output[0] if isinstance(result.output, list) else result.output
            print(f"  FASHN Output: {fashn_url}")

            # Upload to S3
            print(f"  Uploading to S3...")
            s3_url = upload_generated_image(fashn_url, f"{collection_slug}_p2m")

            return {
                "status": "success",
                "collection": collection_slug,
                "fashn_url": fashn_url,
                "s3_url": s3_url
            }
        else:
            print(f"  FAILED: {result.status}")
            if hasattr(result, 'error'):
                print(f"  Error: {result.error}")
            return {
                "status": "failed",
                "collection": collection_slug,
                "error": str(getattr(result, 'error', 'Unknown error'))
            }

    except Exception as e:
        print(f"  Exception: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "collection": collection_slug,
            "error": str(e)
        }


def generate_single(collection_slug: str, resolution: str = "4k") -> dict:
    """Generate single collection image"""
    if collection_slug not in COLLECTION_GARMENTS:
        print(f"Unknown collection: {collection_slug}")
        print(f"Available: {list(COLLECTION_GARMENTS.keys())}")
        return None

    product_url = COLLECTION_GARMENTS[collection_slug]
    return generate_product_to_model(product_url, collection_slug, resolution=resolution)


def generate_all(resolution: str = "4k"):
    """Generate all collection images"""
    results = []

    for slug, product_url in COLLECTION_GARMENTS.items():
        result = generate_product_to_model(product_url, slug, resolution=resolution)
        results.append(result)
        time.sleep(2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    print(f"\nSuccessful: {len(success)}")
    for r in success:
        print(f"  [OK] {r['collection']}: {r['s3_url']}")

    if failed:
        print(f"\nFailed: {len(failed)}")
        for r in failed:
            print(f"  [FAIL] {r['collection']}: {r.get('error', 'Unknown')}")

    return results


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("FASHN Product-to-Model Generator")
    print("=" * 60)

    if len(sys.argv) > 1:
        collection = sys.argv[1]
        resolution = sys.argv[2] if len(sys.argv) > 2 else "4k"

        if collection == "all":
            generate_all(resolution)
        else:
            result = generate_single(collection, resolution)
            if result:
                print(f"\nResult: {result}")
    else:
        print("\nUsage:")
        print("  python generate_product_to_model.py <collection-slug> [resolution]")
        print("  python generate_product_to_model.py all [resolution]")
        print("\nResolution: 1k (catalog) or 4k (high-def)")
        print("\nAvailable collections:")
        for slug in COLLECTION_GARMENTS.keys():
            print(f"  - {slug}")
        print("\nExample:")
        print("  python generate_product_to_model.py tuxedo 4k")
