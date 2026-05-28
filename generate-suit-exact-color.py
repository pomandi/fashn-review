"""
Generate Suit with Exact Fabric Color
Uses extracted color codes and style references
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

# V2535 Fabric exact colors (extracted from analysis)
FABRIC_COLOR = {
    "hex": "#6d9b9f",
    "rgb": (109, 155, 159),
    "name": "Cadet Blue / Muted Teal",
    "hsl": (184, 20, 52)
}

def image_to_base64_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = Path(image_path).suffix.lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{data}"

def generate_with_ideogram_style_ref(fabric_path: str, output_path: str) -> dict:
    """
    Ideogram v3 with fabric as style reference
    """
    print("\n=== IDEOGRAM V3 - Fabric as Style Reference ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # Convert fabric to base64
    fabric_base64 = image_to_base64_url(fabric_path)

    prompt = f"""Professional fashion photography of a tall elegant European man, age 28-32.
Wearing a perfectly tailored 3-piece slim fit Italian suit (jacket, waistcoat, trousers).
The suit color must match the reference image exactly - a muted teal/cadet blue shade.
Fine Super 100s wool fabric with subtle texture.
Modern slim fit, clean lines, Italian tailoring.
White dress shirt.
Standing confidently, full body visible, hands relaxed.
Soft blurred background, warm natural daylight.
High-end fashion catalog photography, studio quality, sharp focus."""

    payload = {
        "prompt": prompt,
        "image_urls": [fabric_base64],  # Fabric as style reference
        "aspect_ratio": "3:4",
        "style": "REALISTIC",
        "magic_prompt_option": "ON",
        "num_images": 1
    }

    print(f"Using fabric as style reference...")
    print(f"Target color: {FABRIC_COLOR['hex']} ({FABRIC_COLOR['name']})")

    response = requests.post(
        "https://fal.run/fal-ai/ideogram/v3",
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
            return {"success": True, "url": img_url, "method": "ideogram_style_ref"}

    print(f"Error: {response.status_code}")
    print(response.text[:500] if response.text else "")
    return {"success": False, "error": response.text}

def generate_with_ideogram_color_palette(fabric_path: str, output_path: str) -> dict:
    """
    Ideogram v3 with custom color palette
    """
    print("\n=== IDEOGRAM V3 - Custom Color Palette ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    # Custom color palette based on fabric
    color_palette = {
        "members": [
            {"color_hex": FABRIC_COLOR["hex"]},  # Main fabric color
            {"color_hex": "#5a8689"},  # Slightly darker shade
            {"color_hex": "#80adaf"},  # Slightly lighter shade
            {"color_hex": "#ffffff"},  # White for shirt
        ]
    }

    prompt = f"""Professional fashion photography of a tall elegant European man, age 28-32.
Wearing a perfectly tailored 3-piece slim fit Italian suit (jacket, waistcoat, trousers).
Suit color: {FABRIC_COLOR['name']}, hex {FABRIC_COLOR['hex']}, a muted teal-blue shade.
Fine Super 100s wool fabric with subtle diagonal weave texture.
Modern slim fit, clean lines, Italian tailoring.
White dress shirt.
Standing confidently, full body visible.
Soft blurred background, warm natural daylight.
High-end fashion catalog photography, studio quality."""

    payload = {
        "prompt": prompt,
        "color_palette": color_palette,
        "aspect_ratio": "3:4",
        "style": "REALISTIC",
        "magic_prompt_option": "ON",
        "num_images": 1
    }

    print(f"Using custom color palette with {FABRIC_COLOR['hex']}...")

    response = requests.post(
        "https://fal.run/fal-ai/ideogram/v3",
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
            return {"success": True, "url": img_url, "method": "ideogram_color_palette"}

    print(f"Error: {response.status_code}")
    print(response.text[:500] if response.text else "")
    return {"success": False, "error": response.text}

def generate_with_recraft_exact_color(output_path: str) -> dict:
    """
    Recraft v3 with exact RGB color
    """
    print("\n=== RECRAFT V3 - Exact RGB Color ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    r, g, b = FABRIC_COLOR["rgb"]

    prompt = f"""Professional fashion photography of a tall elegant European man, age 28-32.
Wearing a perfectly tailored 3-piece slim fit Italian suit (jacket, waistcoat, trousers).
The suit is {FABRIC_COLOR['name']} color, a muted teal shade.
Fine wool fabric with subtle texture.
Modern slim fit, clean lines.
White dress shirt, matching tie.
Standing confidently, full body visible.
Soft blurred background, warm natural daylight.
High-end fashion catalog photography, studio quality, sharp focus on suit."""

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "style": "realistic_image",
        "colors": [{"r": r, "g": g, "b": b}],
        "output_format": "png"
    }

    print(f"Using exact RGB: ({r}, {g}, {b})")

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
            return {"success": True, "url": img_url, "method": "recraft_rgb"}

    print(f"Error: {response.status_code}")
    print(response.text[:500] if response.text else "")
    return {"success": False, "error": response.text}

def generate_with_flux_exact_color(output_path: str) -> dict:
    """
    Flux Pro with very specific color description including hex
    """
    print("\n=== FLUX PRO - Exact Color Description ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    r, g, b = FABRIC_COLOR["rgb"]

    prompt = f"""Professional fashion editorial photography.
Tall elegant blond Dutch man, age 28-32, refined features, clean-shaven.
Wearing a perfectly tailored 3-piece slim fit suit: jacket, waistcoat vest, and trousers.
IMPORTANT: The suit color is EXACTLY {FABRIC_COLOR['hex']} - a muted cadet blue / teal shade.
This is NOT bright teal, NOT sage green, NOT dark blue.
The color is a soft, muted, grayish teal-blue, like the color hex {FABRIC_COLOR['hex']}.
RGB value: {r}, {g}, {b}. Similar to Cadet Blue.
Fine Super 100s wool fabric with subtle diagonal twill weave texture.
Italian tailoring, clean modern lines, slim contemporary fit.
White dress shirt.
Standing confidently with full body visible, relaxed pose.
Soft out-of-focus urban background, warm natural daylight.
Studio-quality lighting, perfect exposure, high-end catalog quality.
8K resolution, sharp focus on suit fabric texture and color."""

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 30,  # More steps for better quality
        "guidance_scale": 4.5,  # Higher guidance for color accuracy
        "num_images": 1,
        "enable_safety_checker": False,
        "output_format": "png"
    }

    print(f"Using detailed color description with hex {FABRIC_COLOR['hex']}...")

    response = requests.post(
        "https://fal.run/fal-ai/flux-pro/v1.1",
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
            return {"success": True, "url": img_url, "method": "flux_detailed"}

    print(f"Error: {response.status_code}")
    print(response.text[:500] if response.text else "")
    return {"success": False, "error": response.text}


if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    output_dir = Path(__file__).parent / "output" / "exact-color-tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SUIT GENERATION WITH EXACT FABRIC COLOR")
    print("=" * 70)
    print(f"Target Color: {FABRIC_COLOR['hex']} ({FABRIC_COLOR['name']})")
    print(f"RGB: {FABRIC_COLOR['rgb']}")
    print("=" * 70)

    results = []

    # Method 1: Ideogram with fabric as style reference
    r1 = generate_with_ideogram_style_ref(
        fabric_path,
        str(output_dir / "v2535_ideogram_style_ref.png")
    )
    results.append(r1)

    # Method 2: Ideogram with color palette
    r2 = generate_with_ideogram_color_palette(
        fabric_path,
        str(output_dir / "v2535_ideogram_palette.png")
    )
    results.append(r2)

    # Method 3: Recraft with exact RGB
    r3 = generate_with_recraft_exact_color(
        str(output_dir / "v2535_recraft_rgb.png")
    )
    results.append(r3)

    # Method 4: Flux with detailed description
    r4 = generate_with_flux_exact_color(
        str(output_dir / "v2535_flux_detailed.png")
    )
    results.append(r4)

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    for r in results:
        if r.get("success"):
            print(f"[OK] {r['method']}")
        else:
            print(f"[FAIL] {r.get('method', 'unknown')}: {r.get('error', '')[:100]}")

    print(f"\nOutput folder: {output_dir}")
