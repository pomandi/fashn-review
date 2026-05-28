"""
Test FASHN API with official Python SDK
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Install: pip install fashn
from fashn import Fashn

API_KEY = os.getenv("FASHN_API_KEY")

# Koleksiyon resimleri (S3'ten)
COLLECTION_IMAGES = {
    "tuxedo": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-09-04_at_09.17.59_616cab49_thumbnail_4096.jpeg",
    "black-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.54_59449144_thumbnail_4096.jpeg",
    "blue-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.25_9dce9985_thumbnail_4096.jpeg",
    "beige-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/Beige_trouwpak_5_a70a4b44_thumbnail_4096.jpeg",
}

# Profesyonel model fotoğrafı - tam vücut erkek model
MODEL_IMAGE = "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800"


def test_tryon(garment_url: str, model_url: str = MODEL_IMAGE):
    """Test virtual try-on with FASHN SDK"""

    print("=" * 60)
    print("FASHN Virtual Try-On Test (Official SDK)")
    print("=" * 60)
    print()
    print(f"API Key: {API_KEY[:15]}...{API_KEY[-5:]}")
    print(f"Model: {model_url[:50]}...")
    print(f"Garment: {garment_url[:50]}...")
    print()

    client = Fashn(api_key=API_KEY)

    print("Sending request...")

    try:
        result = client.predictions.subscribe(
            model_name="tryon-v1.6",
            inputs={
                "garment_image": garment_url,
                "model_image": model_url,
                "category": "one-pieces",  # Full suit
                "mode": "quality",
                "garment_photo_type": "model",
            },
            on_enqueued=lambda pid: print(f"  Queued: {pid}"),
            on_queue_update=lambda status: print(f"  Status: {status.status}"),
        )

        print()
        print("=" * 60)
        print("RESULT:")
        print(f"  Status: {result.status}")
        print(f"  Output: {result.output}")
        print("=" * 60)

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    # Test with tuxedo collection image
    test_tryon(COLLECTION_IMAGES["tuxedo"])
