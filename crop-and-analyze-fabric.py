"""
Crop fabric to center, analyze texture/pattern, generate with Flux Pro
"""
import os
import base64
import requests
from pathlib import Path
from PIL import Image
import colorsys
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

FAL_KEY = os.getenv("FAL_KEY")

def crop_fabric_only(image_path: str, output_path: str) -> str:
    """Crop to fabric area only, removing wood background"""
    print("\n=== CROPPING FABRIC ===")

    img = Image.open(image_path)
    width, height = img.size
    print(f"Original size: {width}x{height}")

    # The fabric is roughly in the center-right area
    # Looking at the image:
    # - Left edge has some wood
    # - Right side is the fabric swatch
    # - Bottom has the label
    # - Top has zigzag edge

    # Crop to just the fabric (avoiding label, edges, wood)
    # Fabric area approximately:
    left = int(width * 0.35)   # Start after the left wood/book edge
    right = int(width * 0.95)  # Before right edge
    top = int(height * 0.05)   # Just below zigzag
    bottom = int(height * 0.65) # Above the label

    fabric_crop = img.crop((left, top, right, bottom))
    fabric_crop.save(output_path)

    print(f"Cropped size: {fabric_crop.size}")
    print(f"Saved to: {output_path}")

    return output_path

def analyze_fabric_texture(image_path: str) -> dict:
    """Analyze fabric texture and pattern details"""
    print("\n=== ANALYZING FABRIC TEXTURE ===")

    img = Image.open(image_path).convert('RGB')
    width, height = img.size

    # Sample pixels for color
    pixels = list(img.getdata())

    # Filter out very bright/dark (potential noise)
    filtered = [(r,g,b) for r,g,b in pixels if 40 < (r+g+b)/3 < 220]

    if filtered:
        avg_r = sum(p[0] for p in filtered) // len(filtered)
        avg_g = sum(p[1] for p in filtered) // len(filtered)
        avg_b = sum(p[2] for p in filtered) // len(filtered)
    else:
        avg_r, avg_g, avg_b = 109, 155, 159  # fallback

    hex_color = f"#{avg_r:02x}{avg_g:02x}{avg_b:02x}"
    h, l, s = colorsys.rgb_to_hls(avg_r/255, avg_g/255, avg_b/255)

    print(f"Average RGB: ({avg_r}, {avg_g}, {avg_b})")
    print(f"HEX: {hex_color}")
    print(f"HSL: H:{int(h*360)} S:{int(s*100)}% L:{int(l*100)}%")

    # Analyze texture by looking at pixel variance
    # High variance = more texture visible
    variances = []
    sample_size = 20
    for i in range(0, len(filtered)-sample_size, sample_size):
        sample = filtered[i:i+sample_size]
        avg = sum(sum(p) for p in sample) / (len(sample) * 3)
        var = sum((sum(p)/3 - avg)**2 for p in sample) / len(sample)
        variances.append(var)

    avg_variance = sum(variances) / len(variances) if variances else 0
    print(f"Texture variance: {avg_variance:.2f}")

    # Describe the fabric
    # Based on V2535: Super 100s wool, 275g/m
    # This is a fine worsted wool with diagonal twill weave

    texture_description = """
    - Fabric type: Fine worsted wool (Super 100s)
    - Weight: Medium (275g/m)
    - Weave: Diagonal twill weave (subtle diagonal lines visible)
    - Finish: Smooth with slight sheen
    - Texture: Fine, even, with subtle diagonal ribbing
    """

    print(texture_description)

    return {
        "rgb": (avg_r, avg_g, avg_b),
        "hex": hex_color,
        "hsl": (int(h*360), int(s*100), int(l*100)),
        "variance": avg_variance,
        "description": "fine worsted wool with diagonal twill weave, subtle sheen"
    }

def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/jpeg;base64,{data}"

def generate_with_flux_detailed(color_info: dict, output_path: str, attempt: int = 1) -> dict:
    """Generate with Flux Pro using detailed fabric description"""
    print(f"\n=== FLUX PRO - Attempt {attempt} ===")

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json"
    }

    r, g, b = color_info["rgb"]
    hex_color = color_info["hex"]
    h, s, l = color_info["hsl"]

    # Very detailed prompt focusing on exact color and texture
    prompts = [
        # Attempt 1: Focus on exact color with hex
        f"""Professional fashion photography, studio quality.
A tall elegant blond Dutch man, age 28-32, refined features, clean-shaven.
Wearing a perfectly tailored 3-piece slim fit suit: jacket, waistcoat, and trousers.

CRITICAL COLOR SPECIFICATION:
The suit fabric color is EXACTLY {hex_color} (RGB: {r},{g},{b}).
This is a muted teal-green, similar to eucalyptus or seafoam with gray undertones.
NOT bright turquoise. NOT dark navy. NOT sage green.
The exact shade is between teal and cadet blue - a sophisticated muted cyan-green.

FABRIC TEXTURE:
Fine Super 100s worsted wool fabric.
Subtle diagonal twill weave pattern visible in the fabric.
Smooth finish with slight natural sheen.
The weave creates fine diagonal lines at 45 degrees.

STYLING:
Italian tailoring, modern slim fit, peak lapels on jacket.
Double-breasted waistcoat with 6 buttons.
Flat-front trousers with clean break.
White dress shirt, no tie, top button open.

POSE & SETTING:
Standing confidently with hands in trouser pockets.
Full body visible from head to below knees.
Soft out-of-focus urban Italian background.
Warm golden hour natural lighting, gentle shadows.
High-end fashion editorial quality, 8K resolution.""",

        # Attempt 2: Simpler, more direct
        f"""Fashion catalog photograph.
Handsome blond European man in his early 30s.
Wearing a 3-piece slim fit suit in muted teal color (hex {hex_color}).
The suit color is a soft gray-green, like dusty teal or cadet blue.
Fine wool fabric with subtle diagonal texture.
White shirt, no tie.
Full body shot, confident pose.
Natural daylight, blurred background.
Professional quality.""",

        # Attempt 3: Color comparison approach
        f"""Professional fashion photography of a man wearing a 3-piece suit.
The suit color is {hex_color} - imagine mixing:
- 40% gray
- 35% teal/cyan
- 25% sage green
This creates a sophisticated muted teal-green tone.

The fabric is fine Italian wool with visible diagonal weave.
Slim fit tailoring, modern style.
Blond Dutch model, 30 years old.
Full body visible, studio lighting quality."""
    ]

    prompt = prompts[min(attempt-1, len(prompts)-1)]

    print(f"Using prompt variation {attempt}")
    print(f"Target color: {hex_color}")

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 30,
        "guidance_scale": 4.0,
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
            print(f"Success! URL: {img_url}")

            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"Saved: {output_path}")
            return {"success": True, "url": img_url}

    print(f"Error: {response.status_code}")
    print(response.text[:300])
    return {"success": False}


if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    output_dir = Path(__file__).parent / "output" / "flux-attempts"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("FABRIC CROP, ANALYZE & GENERATE")
    print("=" * 70)

    # Step 1: Crop fabric
    cropped_path = str(output_dir / "v2535_cropped.jpg")
    crop_fabric_only(fabric_path, cropped_path)

    # Step 2: Analyze cropped fabric
    color_info = analyze_fabric_texture(cropped_path)

    print("\n" + "=" * 70)
    print("GENERATING WITH FLUX PRO - 3 ATTEMPTS")
    print("=" * 70)

    # Step 3: Generate with 3 different prompt variations
    for i in range(1, 4):
        output_path = str(output_dir / f"v2535_flux_attempt_{i}.png")
        generate_with_flux_detailed(color_info, output_path, attempt=i)

    print("\n" + "=" * 70)
    print(f"DONE - Check {output_dir}")
    print("=" * 70)
