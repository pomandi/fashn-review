"""
Italian street style with bokeh background
"""
import os
import requests
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")

FABRIC = {
    "hex": "#80afb3",
    "rgb": (128, 175, 179),
}

def generate(prompt: str, output_path: str, name: str):
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
            return {"success": True}
    print(f"Error: {response.status_code}")
    return {"success": False}


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output" / "italian-style"
    output_dir.mkdir(parents=True, exist_ok=True)

    r, g, b = FABRIC["rgb"]
    hex_c = FABRIC["hex"]

    print("=" * 60)
    print("ITALIAN STREET STYLE - Bokeh Background")
    print(f"Target color: {hex_c}")
    print("=" * 60)

    prompts = {
        "milan_fashion": f"""Cinematic fashion photography in Milan, Italy.
Tall elegant blond Dutch man, age 30, refined sharp features.
Wearing a perfectly tailored 3-piece slim fit suit in color {hex_c}.
The suit is light muted teal, soft aqua tone, fine Super 100s wool.

BACKGROUND: Beautiful blurred Milan fashion district street.
Soft bokeh lights, historic Italian architecture out of focus.
Warm golden hour sunlight, romantic Italian atmosphere.
Shallow depth of field, f/1.8 aperture effect.

White dress shirt, open collar, no tie.
Standing confidently, hands in trouser pockets.
Full body from head to knees visible.
Editorial fashion quality, 8K, cinematic color grading.""",

        "florence_evening": f"""Professional fashion editorial in Florence, Italy.
Handsome blond European man, early 30s, elegant features.
Wearing a 3-piece slim fit Italian suit, color {hex_c} - light teal.
Fine wool fabric with subtle diagonal weave texture.

BACKGROUND: Dreamy blurred Florence street at golden hour.
Soft out-of-focus Italian buildings, warm amber bokeh lights.
Romantic European atmosphere, cinematic shallow depth of field.
The background is completely blurred, focus only on the man.

White shirt, no tie, sophisticated casual look.
Relaxed confident pose, full body visible.
High-end fashion catalog quality, warm color tones.""",

        "rome_sunset": f"""Fashion photography at sunset in Rome, Italy.
Elegant blond Dutch man, 30 years old, model features.
3-piece slim fit suit in {hex_c} - muted aqua/teal shade.
Super 100s wool, diagonal twill weave, Italian tailoring.

BACKGROUND: Heavily blurred Roman street with warm sunset glow.
Beautiful bokeh circles from street lights and sun flares.
Historic Italian architecture completely out of focus.
Dreamy, romantic, cinematic atmosphere.
Very shallow depth of field, only the man is sharp.

Crisp white shirt, collar open, no tie.
Standing tall, confident pose, full body shot.
Luxury fashion editorial, magazine quality, 8K resolution.""",

        "como_lakeside": f"""Luxury fashion shoot near Lake Como, Italy.
Tall blond Dutch gentleman, age 28-32, refined features.
Impeccable 3-piece suit in {hex_c} - soft teal/aquamarine.
Fine Italian wool, slim modern fit, perfect tailoring.

BACKGROUND: Dreamy blurred Italian lakeside town.
Soft pastel buildings and greenery completely out of focus.
Warm Mediterranean light, gentle bokeh, romantic mood.
Background is a beautiful blur of colors and light.

White dress shirt, open at collar.
Elegant confident stance, hands casually in pockets.
Full body visible, sharp focus on suit.
Vogue Italia editorial quality, cinematic lighting."""
    }

    for name, prompt in prompts.items():
        output_path = str(output_dir / f"v2535_{name}.png")
        generate(prompt, output_path, name)

    print("\n" + "=" * 60)
    print(f"DONE - {output_dir}")
