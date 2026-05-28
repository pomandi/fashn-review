"""
Direct Fabric Reference - Uses fabric image as style reference
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

def generate_with_fabric_reference(fabric_path: str, output_path: str) -> dict:
    """
    Use fabric image as direct color/style reference
    """
    print("\n=== Flux General with fabric as reference ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # Convert fabric to base64
    fabric_base64 = image_to_base64_url(fabric_path)
    print(f"Fabric image converted to base64")

    # Prompt focuses on the suit, reference image provides the color
    prompt = """Professional fashion photography.
Tall elegant blond Dutch man, age 28-32.
Wearing a tailored 3-piece slim fit suit: jacket, waistcoat, trousers.
The suit color and fabric texture should match the reference image exactly.
Fine wool fabric with subtle sheen.
Italian style tailoring, modern slim fit.
White dress shirt, matching tie.
Standing confidently, full body visible.
Soft blurred background, warm natural daylight.
High-end fashion catalog, sharp focus."""

    payload = {
        "prompt": prompt,
        "reference_image_url": fabric_base64,
        "reference_strength": 0.75,  # Strong reference for color matching
        "image_size": "portrait_4_3",
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "enable_safety_checker": False,
        "output_format": "png"
    }

    print("Calling Flux General with fabric reference...")
    response = requests.post(
        "https://fal.run/fal-ai/flux-general/image-to-image",
        headers=headers,
        json=payload,
        timeout=180
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

    print(f"Error: {response.status_code}")
    print(response.text[:500])
    return {"success": False, "error": response.text}

def generate_with_flux_redux(fabric_path: str, output_path: str) -> dict:
    """
    Try Flux Redux which is designed for style reference
    """
    print("\n=== Flux Pro Redux - Style Reference ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    fabric_base64 = image_to_base64_url(fabric_path)

    # Redux uses image as primary style reference
    payload = {
        "image_url": fabric_base64,
        "prompt": """Transform this into a professional fashion photo of a tall elegant blond Dutch man
wearing a 3-piece slim fit suit in this exact fabric color and texture.
Italian tailoring, modern slim fit, jacket, waistcoat, trousers.
Full body visible, confident pose, fashion catalog quality.""",
        "num_images": 1,
        "enable_safety_checker": False,
        "output_format": "png"
    }

    print("Calling Flux Redux...")
    response = requests.post(
        "https://fal.run/fal-ai/flux-pro/redux",
        headers=headers,
        json=payload,
        timeout=180
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

    print(f"Error: {response.status_code}")
    print(response.text[:500] if response.text else "No response")
    return {"success": False, "error": response.text}

def generate_with_recraft_colors(fabric_path: str, output_path: str) -> dict:
    """
    Recraft v3 with extracted colors from fabric
    """
    print("\n=== Recraft v3 with color palette ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # V2535 fabric colors extracted manually (teal/mint green tones)
    # Looking at the fabric: main color is a teal/cyan-green
    fabric_colors = [
        {"r": 95, "g": 140, "b": 130},   # Main teal green
        {"r": 85, "g": 130, "b": 120},   # Slightly darker
        {"r": 105, "g": 150, "b": 140},  # Slightly lighter
    ]

    prompt = """Professional fashion photography of a tall elegant blond European man, age 28-32.
Wearing a perfectly tailored 3-piece slim fit suit: jacket, waistcoat vest, and trousers.
Fine Super 100s wool fabric with subtle texture.
Italian style tailoring, clean modern lines.
White dress shirt.
Standing confidently with full body visible, relaxed pose.
Soft blurred urban background, warm natural daylight.
High-end fashion catalog photography, studio quality."""

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "style": "realistic_image",
        "colors": fabric_colors,
        "output_format": "png"
    }

    print("Calling Recraft v3 with extracted colors...")
    response = requests.post(
        "https://fal.run/fal-ai/recraft/v3/text-to-image",
        headers=headers,
        json=payload,
        timeout=180
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

    print(f"Error: {response.status_code}")
    print(response.text[:500] if response.text else "No response")
    return {"success": False, "error": response.text}


if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    output_dir = Path(__file__).parent / "output" / "fabric-tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DIRECT FABRIC REFERENCE - V2535")
    print("=" * 60)

    results = []

    # Method 1: Flux General with reference_image
    r1 = generate_with_fabric_reference(
        fabric_path,
        str(output_dir / "v2535_flux_general_ref.png")
    )
    results.append(("Flux General Reference", r1))

    # Method 2: Flux Redux
    r2 = generate_with_flux_redux(
        fabric_path,
        str(output_dir / "v2535_flux_redux.png")
    )
    results.append(("Flux Redux", r2))

    # Method 3: Recraft with colors
    r3 = generate_with_recraft_colors(
        fabric_path,
        str(output_dir / "v2535_recraft_colors.png")
    )
    results.append(("Recraft Colors", r3))

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, r in results:
        status = "OK" if r.get("success") else "FAILED"
        print(f"{name}: {status}")
