"""
FASHN AI Virtual Try-On Example
Demonstrates how to use the Virtual Try-On v1.6 API
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("FASHN_API_KEY")
BASE_URL = "https://fal.run/fal-ai/fashn/tryon/v1.6"


def virtual_tryon(model_image_url: str, garment_image_url: str, **kwargs) -> dict:
    """
    Perform virtual try-on using FASHN API

    Args:
        model_image_url: URL of the model/person image
        garment_image_url: URL of the garment image
        **kwargs: Optional parameters:
            - category: 'auto', 'tops', 'bottoms', 'one-pieces'
            - mode: 'performance', 'balanced', 'quality'
            - garment_photo_type: 'auto', 'model', 'flat-lay'
            - num_samples: 1-4
            - output_format: 'png', 'jpeg'

    Returns:
        dict with 'images' array containing generated image URLs
    """
    headers = {
        "Authorization": f"Key {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model_image": model_image_url,
        "garment_image": garment_image_url,
        "category": kwargs.get("category", "auto"),
        "mode": kwargs.get("mode", "balanced"),
        "garment_photo_type": kwargs.get("garment_photo_type", "auto"),
        "num_samples": kwargs.get("num_samples", 1),
        "output_format": kwargs.get("output_format", "png"),
        "segmentation_free": kwargs.get("segmentation_free", True),
    }

    # Add optional seed for reproducibility
    if "seed" in kwargs:
        payload["seed"] = kwargs["seed"]

    response = requests.post(BASE_URL, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()


def download_image(url: str, output_path: str) -> None:
    """Download image from URL to local file"""
    response = requests.get(url)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"Image saved to: {output_path}")


if __name__ == "__main__":
    # Example usage
    MODEL_IMAGE = "https://storage.googleapis.com/falserverless/example_inputs/model.png"
    GARMENT_IMAGE = "https://storage.googleapis.com/falserverless/example_inputs/garment.webp"

    print("Starting virtual try-on...")
    print(f"Model: {MODEL_IMAGE}")
    print(f"Garment: {GARMENT_IMAGE}")
    print()

    try:
        result = virtual_tryon(
            model_image_url=MODEL_IMAGE,
            garment_image_url=GARMENT_IMAGE,
            category="auto",
            mode="balanced"  # Options: performance, balanced, quality
        )

        print("Success!")
        print(f"Generated {len(result['images'])} image(s)")

        for i, image in enumerate(result["images"]):
            print(f"  Image {i+1}: {image['url']}")

            # Optionally download the image
            # download_image(image['url'], f"output_{i}.png")

    except requests.exceptions.HTTPError as e:
        print(f"API Error: {e}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")
