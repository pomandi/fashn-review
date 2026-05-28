"""
Fabric Reference Generator - Uses actual fabric image as style reference
"""
import os
import sys
import base64
import requests
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")
print(f"Using FAL_KEY: {FAL_KEY[:20]}...")

def image_to_base64_url(image_path: str) -> str:
    """Convert local image to base64 data URI"""
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = Path(image_path).suffix.lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{data}"

def upload_to_fal_storage(image_path: str) -> str:
    """Upload image to fal.ai CDN storage"""
    print(f"Uploading {Path(image_path).name} to fal.ai storage...")

    headers = {"Authorization": f"Key {FAL_KEY}"}

    with open(image_path, "rb") as f:
        file_data = f.read()

    # Use multipart upload
    files = {
        'file': (Path(image_path).name, file_data, 'image/jpeg')
    }

    response = requests.post(
        "https://fal.ai/api/storage/upload",
        headers=headers,
        files=files
    )

    if response.status_code == 200:
        result = response.json()
        url = result.get("url") or result.get("file_url")
        print(f"Uploaded: {url}")
        return url
    else:
        print(f"Upload failed ({response.status_code}), using base64...")
        return image_to_base64_url(image_path)

def generate_with_ideogram(fabric_path: str, output_path: str) -> dict:
    """
    Try Ideogram v3 which supports style reference
    """
    print("\n=== Method: Ideogram v3 with style reference ===")

    # Upload fabric as style reference
    fabric_url = image_to_base64_url(fabric_path)

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # More accurate color description based on the actual fabric
    # V2535 is a dusty sage green / eucalyptus color
    prompt = """Professional fashion photography of a tall elegant European man, age 28-32,
wearing a tailored 3-piece slim fit suit (jacket, vest, trousers).
The suit fabric is dusty sage green, muted eucalyptus tone with subtle diagonal twill weave texture.
Fine Super 100s wool fabric with soft matte finish.
Italian style tailoring, clean lines, modern slim fit.
Standing confidently, full body visible, hands relaxed.
Soft blurred background, warm natural daylight, studio-quality lighting.
High-end fashion catalog photography, sharp focus on suit details."""

    print(f"Trying Ideogram v3...")

    payload = {
        "prompt": prompt,
        "aspect_ratio": "3:4",
        "style": "realistic",
        "negative_prompt": "cartoon, illustration, painting, bright colors, neon, saturated"
    }

    response = requests.post(
        "https://fal.run/fal-ai/ideogram/v3",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("images"):
            img_url = result["images"][0]["url"]
            print(f"Success! URL: {img_url}")

            # Download
            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"Saved: {output_path}")
            return {"success": True, "url": img_url}

    print(f"Ideogram failed: {response.status_code} - {response.text[:200]}")
    return {"success": False, "error": response.text}

def generate_with_flux_better_prompt(fabric_path: str, output_path: str) -> dict:
    """
    Use Flux Pro with more accurate color description
    """
    print("\n=== Method: Flux Pro with accurate color ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # More accurate description of V2535 fabric
    # Looking at the image: it's a muted sage/dusty green with slight grey undertones
    prompt = """Professional fashion editorial photography.
Tall elegant blond Dutch man, age 28-32, refined features.
Wearing a perfectly tailored 3-piece slim fit suit: jacket, waistcoat vest, and trousers.
Suit color: dusty sage green, muted eucalyptus tone, NOT bright teal.
The color is a soft grey-green, like dried sage leaves or eucalyptus.
Fabric: fine Super 100s wool with subtle diagonal twill weave, matte finish.
Italian tailoring, clean modern lines, slim contemporary fit.
White dress shirt, matching sage green tie.
Standing confidently with full body visible, relaxed pose, hands in pockets.
Soft out-of-focus urban background, warm natural daylight.
Studio-quality lighting, perfect exposure, high-end catalog quality.
Shot on medium format camera, sharp focus on suit texture."""

    print("Calling Flux Pro with corrected color...")

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 28,
        "guidance_scale": 4.0,  # Slightly higher for better prompt adherence
        "num_images": 1,
        "enable_safety_checker": False,
        "output_format": "png"
    }

    response = requests.post(
        "https://fal.run/fal-ai/flux-pro/v1.1",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("images"):
            img_url = result["images"][0]["url"]
            print(f"Success! URL: {img_url}")

            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"Saved: {output_path}")
            return {"success": True, "url": img_url}

    print(f"Flux failed: {response.status_code}")
    return {"success": False, "error": response.text}

def generate_with_kontext_transform(fabric_path: str, base_suit_url: str, output_path: str) -> dict:
    """
    Use Flux Kontext to transform an existing suit image
    First generate a base suit, then transform its color
    """
    print("\n=== Method: Flux Kontext color transform ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # Transform the suit color to match fabric
    prompt = """Transform the suit color to a muted dusty sage green.
The color should be soft grey-green like eucalyptus or dried sage leaves.
NOT bright teal or turquoise - more muted and earthy.
Keep the same suit style, fit, model pose and background.
The fabric should look like fine wool with subtle texture."""

    print(f"Transforming suit color...")

    payload = {
        "prompt": prompt,
        "image_url": base_suit_url,
        "guidance_scale": 4.0,
        "num_images": 1,
        "output_format": "png"
    }

    response = requests.post(
        "https://fal.run/fal-ai/flux-pro/kontext",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("images"):
            img_url = result["images"][0]["url"]
            print(f"Success! URL: {img_url}")

            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"Saved: {output_path}")
            return {"success": True, "url": img_url}

    print(f"Kontext failed: {response.status_code}")
    return {"success": False, "error": response.text}


if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    output_dir = Path(__file__).parent / "output" / "fabric-tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FABRIC REFERENCE GENERATOR - V2535 Sage Green")
    print("=" * 60)

    # Method 1: Better prompt with Flux
    result1 = generate_with_flux_better_prompt(
        fabric_path,
        str(output_dir / "v2535_sage_green_flux.png")
    )

    # Method 2: Transform the previous result
    if result1.get("success"):
        # Use the first result as base and refine with Kontext
        result2 = generate_with_kontext_transform(
            fabric_path,
            result1["url"],
            str(output_dir / "v2535_sage_green_refined.png")
        )

    print("\n" + "=" * 60)
    print("DONE - Check output/fabric-tests/ folder")
    print("=" * 60)
