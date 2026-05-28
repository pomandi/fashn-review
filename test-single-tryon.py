"""
Test FASHN API with a single collection image
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("FASHN_API_KEY")
BASE_URL = "https://fal.run/fal-ai/fashn/tryon/v1.6"

# Koleksiyon resimleri (S3'ten)
COLLECTION_IMAGES = {
    "tuxedo": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-09-04_at_09.17.59_616cab49_thumbnail_4096.jpeg",
    "black-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.54_59449144_thumbnail_4096.jpeg",
    "blue-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.25_9dce9985_thumbnail_4096.jpeg",
    "beige-suit": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/Beige_trouwpak_5_a70a4b44_thumbnail_4096.jpeg",
}

# Örnek model resmi (profesyonel erkek model)
# Bu URL'yi gerçek bir model fotoğrafıyla değiştirmemiz gerekecek
SAMPLE_MODEL_IMAGE = "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800"


def test_tryon(garment_url: str, model_url: str = SAMPLE_MODEL_IMAGE):
    """Test virtual try-on with given garment"""

    print(f"Testing try-on...")
    print(f"  Model: {model_url[:60]}...")
    print(f"  Garment: {garment_url[:60]}...")
    print()

    headers = {
        "Authorization": f"Key {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model_image": model_url,
        "garment_image": garment_url,
        "category": "one-pieces",  # Full suit
        "mode": "quality",  # Best quality
        "garment_photo_type": "model",  # Photo shows garment on a model
        "num_samples": 1,
        "output_format": "png",
        "segmentation_free": True,
    }

    try:
        print("Sending request to FASHN API...")
        response = requests.post(BASE_URL, headers=headers, json=payload, timeout=120)

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("\nSUCCESS!")
            for i, img in enumerate(result.get("images", [])):
                print(f"  Output {i+1}: {img.get('url', 'No URL')}")
            return result
        else:
            print(f"Error: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print("Request timed out (>120s)")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("FASHN Virtual Try-On Test")
    print("=" * 60)
    print()

    # Test with tuxedo collection
    result = test_tryon(COLLECTION_IMAGES["tuxedo"])

    if result and result.get("images"):
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("Check the output URL above to see the result.")
        print("=" * 60)
