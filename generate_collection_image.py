"""
Generate new collection images using FASHN Virtual Try-On API
Uses base model + garment images to create new collection backgrounds
"""

import os
import time
from dotenv import load_dotenv
from fashn import Fashn
from s3_uploader import upload_generated_image, list_s3_folder

load_dotenv()

# Configuration
FASHN_API_KEY = os.getenv("FASHN_API_KEY")
BASE_MODEL_URL = "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/dutch-blond-model.jpeg"

# Current collection images from S3
COLLECTION_GARMENTS = {
    "tuxedo": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-09-04_at_09.17.59_616cab49_thumbnail_4096.jpeg",
    "black-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.54_59449144_thumbnail_4096.jpeg",
    "blue-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.25_9dce9985_thumbnail_4096.jpeg",
    "burgundy-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.52_e35422ce_thumbnail_4096.jpeg",
    "beige-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/Beige_trouwpak_5_a70a4b44_thumbnail_4096.jpeg",
    "gray-wedding-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.05_8fc1e4dc_thumbnail_4096.jpeg",
    "green-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.28.03_0d1d3798_thumbnail_4096.jpeg",
}


def generate_tryon(garment_url: str, collection_slug: str, mode: str = "quality") -> dict:
    """
    Generate virtual try-on image

    Args:
        garment_url: URL of the garment/collection image
        collection_slug: Slug for naming the output
        mode: quality mode (performance, balanced, quality)

    Returns:
        dict with status and output URL
    """
    client = Fashn(api_key=FASHN_API_KEY)

    print(f"\n{'='*60}")
    print(f"Generating: {collection_slug}")
    print(f"{'='*60}")
    print(f"  Model: {BASE_MODEL_URL[:50]}...")
    print(f"  Garment: {garment_url[:50]}...")
    print(f"  Mode: {mode}")
    print()

    try:
        result = client.predictions.subscribe(
            model_name="tryon-v1.6",
            inputs={
                "model_image": BASE_MODEL_URL,
                "garment_image": garment_url,
                "category": "one-pieces",  # Full suit
                "mode": mode,
                "garment_photo_type": "model",  # Garment is shown on a model
                "num_samples": 1,
                "output_format": "png",
            },
            on_enqueued=lambda pid: print(f"  Queued: {pid}"),
            on_queue_update=lambda status: print(f"  Status: {status.status}"),
        )

        print()

        if result.status == "completed" and result.output:
            fashn_url = result.output[0] if isinstance(result.output, list) else result.output
            print(f"  FASHN Output: {fashn_url}")

            # Upload to S3
            print(f"  Uploading to S3...")
            s3_url = upload_generated_image(fashn_url, collection_slug)

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
        return {
            "status": "error",
            "collection": collection_slug,
            "error": str(e)
        }


def generate_single(collection_slug: str) -> dict:
    """Generate single collection image"""
    if collection_slug not in COLLECTION_GARMENTS:
        print(f"Unknown collection: {collection_slug}")
        print(f"Available: {list(COLLECTION_GARMENTS.keys())}")
        return None

    garment_url = COLLECTION_GARMENTS[collection_slug]
    return generate_tryon(garment_url, collection_slug)


def generate_all():
    """Generate all collection images"""
    results = []

    for slug, garment_url in COLLECTION_GARMENTS.items():
        result = generate_tryon(garment_url, slug)
        results.append(result)

        # Small delay between requests
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
    print("FASHN Collection Image Generator")
    print("=" * 60)

    if len(sys.argv) > 1:
        # Generate specific collection
        collection = sys.argv[1]
        result = generate_single(collection)
        if result:
            print(f"\nResult: {result}")
    else:
        # Show help
        print("\nUsage:")
        print("  python generate_collection_image.py <collection-slug>")
        print("  python generate_collection_image.py all")
        print("\nAvailable collections:")
        for slug in COLLECTION_GARMENTS.keys():
            print(f"  - {slug}")
        print("\nExample:")
        print("  python generate_collection_image.py tuxedo")
