"""
Test FASHN API with detailed error logging
"""

import os
from dotenv import load_dotenv

load_dotenv()

from fashn import Fashn

API_KEY = os.getenv("FASHN_API_KEY")

# Koleksiyon resmi - Tuxedo
GARMENT_IMAGE = "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-09-04_at_09.17.59_616cab49_thumbnail_4096.jpeg"

# Farklı model resimleri deneyelim - tam vücut erkek model gerekiyor
MODEL_IMAGES = [
    # Full body man in neutral pose
    "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=800",  # Business man full body
    "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=800",  # Man portrait
]


def test_with_details():
    """Test with detailed output"""

    print("=" * 60)
    print("FASHN Detailed Test")
    print("=" * 60)

    client = Fashn(api_key=API_KEY)

    for i, model_url in enumerate(MODEL_IMAGES):
        print(f"\n--- Test {i+1} ---")
        print(f"Model: {model_url}")

        try:
            # Use lower-level API to get more details
            response = client.predictions.run(
                model_name="tryon-v1.6",
                inputs={
                    "garment_image": GARMENT_IMAGE,
                    "model_image": model_url,
                    "category": "one-pieces",
                    "mode": "balanced",
                    "garment_photo_type": "model",
                },
            )

            print(f"  Prediction ID: {response.id}")

            # Poll for status
            import time
            for _ in range(30):  # Max 60 seconds
                status = client.predictions.status(response.id)
                print(f"  Status: {status.status}")

                if status.status == "completed":
                    print(f"  OUTPUT: {status.output}")
                    break
                elif status.status == "failed":
                    print(f"  FAILED!")
                    # Try to get error details
                    if hasattr(status, 'error'):
                        print(f"  Error: {status.error}")
                    if hasattr(status, 'logs'):
                        print(f"  Logs: {status.logs}")
                    # Print all attributes
                    print(f"  All attrs: {vars(status)}")
                    break

                time.sleep(2)

        except Exception as e:
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_with_details()
