"""
Final attempt with precise color #80afb3
"""
import os
import requests
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")

# Precise color from clean fabric crop
FABRIC = {
    "hex": "#80afb3",
    "rgb": (128, 175, 179),
    "name": "Light Teal / Muted Cyan"
}

def generate(prompt: str, output_path: str, name: str) -> dict:
    print(f"\n=== {name} ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "enable_safety_checker": False,
        "output_format": "png"
    }

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
            print(f"OK: {img_url}")

            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            return {"success": True, "url": img_url}

    print(f"Error: {response.status_code}")
    return {"success": False}


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output" / "final"
    output_dir.mkdir(parents=True, exist_ok=True)

    r, g, b = FABRIC["rgb"]
    hex_c = FABRIC["hex"]

    print("=" * 60)
    print(f"FINAL GENERATION - Target: {hex_c}")
    print("=" * 60)

    prompts = {
        "v1_detailed": f"""Professional fashion editorial photography.
Tall elegant blond Dutch man, age 30, refined features.
Wearing a perfectly tailored 3-piece slim fit suit.

EXACT SUIT COLOR: {hex_c}
This is a light muted teal, soft aqua-cyan tone.
RGB values: {r}, {g}, {b}
Think of a pale seafoam or dusty aquamarine color.

FABRIC DETAILS:
- Fine Super 100s worsted wool
- Visible diagonal twill weave pattern (45 degree lines)
- Smooth finish with subtle natural sheen
- The diagonal texture creates depth

SUIT STYLE:
- Modern slim fit Italian tailoring
- Single-breasted jacket, notch lapels
- Matching waistcoat with 5 buttons
- Flat-front tapered trousers

STYLING: White dress shirt, open collar, no tie.
POSE: Standing confidently, hands in pockets, full body.
BACKGROUND: Soft blurred Italian street, golden hour light.
QUALITY: 8K, fashion catalog, sharp focus on fabric texture.""",

        "v2_simple": f"""Fashion catalog photo of a handsome blond European man in his 30s.
He wears a 3-piece slim fit suit in color {hex_c} - a light muted teal shade.
The suit is fine wool with subtle diagonal weave texture.
White shirt, no tie, confident pose.
Full body visible, soft background, natural light.
High quality professional photography.""",

        "v3_color_focus": f"""A man wearing a light teal 3-piece suit.
The EXACT color is {hex_c} (RGB: {r},{g},{b}).
This color looks like:
- Pale aquamarine
- Dusty seafoam
- Muted cyan with gray
- Light cadet blue

The fabric shows diagonal twill weave lines.
Fine Italian wool, slim fit tailoring.
Blond model, full body, fashion photography."""
    }

    for name, prompt in prompts.items():
        output_path = str(output_dir / f"v2535_{name}.png")
        generate(prompt, output_path, name)

    print("\n" + "=" * 60)
    print(f"DONE - Check {output_dir}")
