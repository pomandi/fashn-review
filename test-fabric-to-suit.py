"""
Fabric to Suit Generator
Uses fal.ai Flux models to generate suit images from fabric swatches
"""
import os
import sys
import base64
import requests
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")
if not FAL_KEY:
    print("ERROR: FAL_KEY not found in .env")
    sys.exit(1)

print(f"Using FAL_KEY: {FAL_KEY[:20]}...")

def image_to_base64(image_path: str) -> str:
    """Convert local image to base64 data URI"""
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = Path(image_path).suffix.lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{data}"

def upload_to_fal(image_path: str) -> str:
    """Upload image to fal.ai storage and get URL"""
    print(f"Uploading {image_path} to fal.ai storage...")

    # Read file
    with open(image_path, "rb") as f:
        file_data = f.read()

    # Get upload URL
    headers = {"Authorization": f"Key {FAL_KEY}"}

    # Use fal storage API
    init_response = requests.post(
        "https://fal.ai/api/storage/upload/initiate",
        headers=headers,
        json={
            "file_name": Path(image_path).name,
            "content_type": f"image/{Path(image_path).suffix.lower().replace('.', '')}"
        }
    )

    if init_response.status_code != 200:
        print(f"Upload init failed: {init_response.text}")
        # Fallback: use base64
        return image_to_base64(image_path)

    upload_data = init_response.json()

    # Upload to presigned URL
    upload_response = requests.put(
        upload_data["upload_url"],
        data=file_data,
        headers={"Content-Type": upload_data.get("content_type", "image/jpeg")}
    )

    if upload_response.status_code in [200, 201]:
        return upload_data["file_url"]
    else:
        print(f"Upload failed: {upload_response.status_code}")
        return image_to_base64(image_path)

def generate_suit_from_fabric(
    fabric_image_path: str,
    suit_style: str = "3-piece slim fit suit",
    model_description: str = "tall elegant Dutch man, age 28-32",
    output_path: str = None
) -> dict:
    """
    Generate a suit image using fabric as color/texture reference

    Args:
        fabric_image_path: Path to fabric swatch image
        suit_style: Type of suit to generate
        model_description: Description of the model
        output_path: Where to save the result
    """

    # First, let's try Flux Pro text-to-image with detailed color description
    # We'll describe the fabric color precisely

    print("\n=== Method 1: Flux Pro with fabric color description ===")

    # Analyze fabric color from image (manual description for now)
    # The V2535 fabric is a mint/teal green Super 100s wool

    fabric_color = "mint teal green"
    fabric_type = "Super 100s fine wool"

    prompt = f"""Professional fashion photography of a {model_description},
wearing a {suit_style} in {fabric_color} {fabric_type} fabric.
The suit has a refined Italian tailoring style with clean lines.
Standing confidently with full body visible, relaxed yet confident pose.
Soft out-of-focus background, warm natural daylight, gentle shadows.
Studio-quality lighting, perfect exposure, high-end catalog quality.
Sharp focus on the suit fabric texture and color."""

    print(f"Prompt: {prompt[:200]}...")

    # Call Flux Pro
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",  # Good for fashion
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "enable_safety_checker": False,
        "output_format": "png"
    }

    print("\nCalling Flux Pro API...")
    response = requests.post(
        "https://fal.run/fal-ai/flux-pro/v1.1",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Success! Generated {len(result.get('images', []))} image(s)")

        if result.get("images"):
            image_url = result["images"][0]["url"]
            print(f"Image URL: {image_url}")

            # Download and save
            if output_path:
                img_response = requests.get(image_url)
                if img_response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)
                    print(f"Saved to: {output_path}")

            return {"success": True, "url": image_url, "result": result}
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return {"success": False, "error": response.text}

def generate_with_image_reference(
    fabric_image_path: str,
    reference_suit_url: str,
    output_path: str = None
) -> dict:
    """
    Use Flux Kontext to change suit color based on fabric reference

    Args:
        fabric_image_path: Path to fabric swatch (for color reference)
        reference_suit_url: URL of a suit image to transform
        output_path: Where to save result
    """

    print("\n=== Method 2: Flux Kontext with image reference ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # The prompt instructs to change the suit color
    prompt = """Change the suit color to mint teal green.
Keep the same style, fit, and model.
The fabric should look like fine Super 100s wool with subtle texture.
Maintain professional fashion photography quality."""

    payload = {
        "prompt": prompt,
        "image_url": reference_suit_url,
        "guidance_scale": 3.5,
        "num_images": 1,
        "output_format": "png"
    }

    print(f"Reference suit: {reference_suit_url}")
    print(f"Prompt: {prompt[:100]}...")

    print("\nCalling Flux Kontext API...")
    response = requests.post(
        "https://fal.run/fal-ai/flux-pro/kontext",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Success!")

        if result.get("images"):
            image_url = result["images"][0]["url"]
            print(f"Image URL: {image_url}")

            if output_path:
                img_response = requests.get(image_url)
                if img_response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)
                    print(f"Saved to: {output_path}")

            return {"success": True, "url": image_url, "result": result}
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return {"success": False, "error": response.text}


if __name__ == "__main__":
    # Fabric image path
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"

    # Output directory
    output_dir = Path(__file__).parent / "output" / "fabric-tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FABRIC TO SUIT GENERATOR")
    print("=" * 60)
    print(f"Fabric: {fabric_path}")
    print(f"Output: {output_dir}")

    # Method 1: Generate with color description
    result1 = generate_suit_from_fabric(
        fabric_image_path=fabric_path,
        suit_style="3-piece slim fit suit with vest",
        model_description="tall elegant blond Dutch man, age 28-32, refined Italian style",
        output_path=str(output_dir / "v2535_method1_flux_pro.png")
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    if result1.get("success"):
        print(f"✓ Method 1 succeeded: {result1['url']}")
    else:
        print(f"✗ Method 1 failed: {result1.get('error', 'Unknown error')}")

    print("\nDone!")
