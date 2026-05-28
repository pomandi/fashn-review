"""
Ideogram V3 with fixed parameters
"""
import os
import base64
import requests
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")

FABRIC_COLOR = {
    "hex": "#6d9b9f",
    "rgb": (109, 155, 159),
    "name": "Cadet Blue / Muted Teal"
}

def image_to_base64_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/jpeg;base64,{data}"

def generate_ideogram_style_ref(fabric_path: str, output_path: str) -> dict:
    """Ideogram with style reference - fixed parameters"""
    print("\n=== IDEOGRAM V3 - Style Reference (Fixed) ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    fabric_base64 = image_to_base64_url(fabric_path)
    r, g, b = FABRIC_COLOR["rgb"]

    prompt = f"""Professional fashion photography of a tall elegant European man.
Wearing a tailored 3-piece slim fit suit (jacket, vest, trousers).
The suit color must match the reference fabric exactly.
Fine wool fabric, Italian tailoring.
White dress shirt.
Full body visible, confident pose.
Soft blurred background, natural daylight.
High-end fashion catalog photography."""

    # Remove style parameter when using image_urls
    payload = {
        "prompt": prompt,
        "image_urls": [fabric_base64],
        "aspect_ratio": "3:4",
        "magic_prompt_option": "ON",
        "num_images": 1
    }

    print("Calling Ideogram with fabric as style reference...")
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
            return {"success": True, "url": img_url}

    print(f"Error: {response.status_code}")
    print(response.text[:500])
    return {"success": False, "error": response.text}

def generate_ideogram_color_palette(output_path: str) -> dict:
    """Ideogram with custom color palette - RGB format"""
    print("\n=== IDEOGRAM V3 - Color Palette (RGB Fixed) ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    r, g, b = FABRIC_COLOR["rgb"]

    prompt = f"""Professional fashion photography of a tall elegant European man.
Wearing a tailored 3-piece slim fit suit (jacket, vest, trousers).
Suit color: muted teal / cadet blue shade.
Fine wool fabric, Italian tailoring.
White dress shirt.
Full body visible, confident pose.
Soft blurred background, natural daylight.
High-end fashion catalog photography."""

    # Fixed color palette with RGB values
    payload = {
        "prompt": prompt,
        "color_palette": {
            "members": [
                {"rgb": {"r": r, "g": g, "b": b}},  # Main fabric color
                {"rgb": {"r": 90, "g": 135, "b": 140}},  # Darker shade
                {"rgb": {"r": 130, "g": 175, "b": 180}},  # Lighter shade
            ]
        },
        "aspect_ratio": "3:4",
        "style": "REALISTIC",
        "magic_prompt_option": "ON",
        "num_images": 1
    }

    print(f"Using RGB palette: ({r}, {g}, {b})")
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
            return {"success": True, "url": img_url}

    print(f"Error: {response.status_code}")
    print(response.text[:500])
    return {"success": False, "error": response.text}


if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    output_dir = Path(__file__).parent / "output" / "exact-color-tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("IDEOGRAM V3 - Fixed Parameters")
    print(f"Target: {FABRIC_COLOR['hex']}")
    print("=" * 60)

    # Style reference
    r1 = generate_ideogram_style_ref(
        fabric_path,
        str(output_dir / "v2535_ideogram_style_fixed.png")
    )

    # Color palette
    r2 = generate_ideogram_color_palette(
        str(output_dir / "v2535_ideogram_palette_fixed.png")
    )

    print("\n" + "=" * 60)
    print("DONE")
