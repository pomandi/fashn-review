"""
Fabric Color Analyzer V2 - Sample from correct fabric area (right side)
"""
import os
from pathlib import Path
from PIL import Image
import colorsys
from collections import Counter

def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def rgb_to_hsl(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
    return (int(h*360), int(s*100), int(l*100))

def get_color_name(r, g, b):
    """Try to find closest color name"""
    colors = {
        "Teal": (0, 128, 128),
        "Teal Green": (0, 130, 127),
        "Cyan": (0, 255, 255),
        "Turquoise": (64, 224, 208),
        "Aquamarine": (127, 255, 212),
        "Sea Green": (46, 139, 87),
        "Medium Sea Green": (60, 179, 113),
        "Light Sea Green": (32, 178, 170),
        "Dark Cyan": (0, 139, 139),
        "Cadet Blue": (95, 158, 160),
        "Steel Blue": (70, 130, 180),
        "Sage Green": (138, 154, 91),
        "Eucalyptus": (68, 145, 130),
        "Seafoam": (120, 195, 170),
        "Mint": (152, 255, 152),
        "Jade": (0, 168, 107),
        "Viridian": (64, 130, 109),
        "Persian Green": (0, 166, 147),
        "Pine Green": (1, 121, 111),
        "Verdigris": (67, 179, 174),
        "Celadon": (172, 225, 175),
        "Cambridge Blue": (163, 193, 173),
        "Opal": (168, 195, 188),
        "Morning Blue": (141, 163, 153),
        "Ash Gray": (178, 190, 181),
        "Dark Sea Green": (143, 188, 143),
        "Hooker's Green": (73, 121, 107),
        "Amazon Green": (59, 122, 87),
        "Patina": (99, 154, 143),
        "Polished Pine": (93, 164, 147),
        "Ocean Green": (72, 191, 145),
        "Wintergreen Dream": (86, 136, 125),
        "Myrtle Green": (49, 120, 115),
        "Deep Sea Green": (9, 88, 89),
        "Skobeloff": (0, 116, 116),
    }

    min_dist = float('inf')
    closest = "Unknown"

    for name, (cr, cg, cb) in colors.items():
        dist = ((r-cr)**2 + (g-cg)**2 + (b-cb)**2) ** 0.5
        if dist < min_dist:
            min_dist = dist
            closest = name

    return closest, min_dist

def analyze_fabric(image_path: str):
    """Analyze fabric image - sample from RIGHT side where fabric is"""
    print(f"\n{'='*60}")
    print(f"FABRIC COLOR ANALYSIS V2: {Path(image_path).name}")
    print(f"{'='*60}")

    img = Image.open(image_path)
    img = img.convert('RGB')

    width, height = img.size
    print(f"Image size: {width}x{height}")

    # The fabric is on the RIGHT side of the image
    # Sample from right-center area, avoiding the label in bottom-right
    # Label is approximately at bottom 1/4

    sample_left = int(width * 0.55)  # Start from 55% of width (right side)
    sample_right = int(width * 0.85)  # End at 85%
    sample_top = int(height * 0.15)   # Start from 15% of height
    sample_bottom = int(height * 0.55) # End at 55% (above label)

    print(f"Sampling area: ({sample_left}, {sample_top}) to ({sample_right}, {sample_bottom})")

    # Crop to fabric area only
    fabric_area = img.crop((sample_left, sample_top, sample_right, sample_bottom))

    # Save sample area for verification
    sample_path = Path(image_path).parent / "V2535_sample_area.jpg"
    fabric_area.save(sample_path)
    print(f"Sample area saved to: {sample_path}")

    # Get all pixels
    pixels = list(fabric_area.getdata())
    total_pixels = len(pixels)
    print(f"Total pixels sampled: {total_pixels}")

    # Count colors (quantize to reduce noise)
    def quantize(color, step=4):  # Smaller step for more precision
        return tuple((c // step) * step for c in color)

    quantized = [quantize(p) for p in pixels]
    color_counts = Counter(quantized)

    # Get top colors
    top_colors = color_counts.most_common(15)

    print(f"\n--- TOP 15 DOMINANT COLORS (from fabric area) ---")
    print(f"{'Rank':<6}{'RGB':<20}{'HEX':<10}{'HSL':<20}{'%':<8}")
    print("-" * 64)

    for i, (color, count) in enumerate(top_colors, 1):
        r, g, b = color
        hex_color = rgb_to_hex(r, g, b)
        hsl = rgb_to_hsl(r, g, b)
        pct = (count / total_pixels) * 100
        print(f"{i:<6}({r:3},{g:3},{b:3}){'':<6}{hex_color:<10}H:{hsl[0]:3} S:{hsl[1]:2}% L:{hsl[2]:2}%{'':<3}{pct:.1f}%")

    # Calculate weighted average (excluding very dark/light outliers)
    filtered_pixels = [(r, g, b) for r, g, b in pixels
                       if 30 < (r+g+b)/3 < 220]  # Exclude very dark/light

    if filtered_pixels:
        avg_r = sum(p[0] for p in filtered_pixels) // len(filtered_pixels)
        avg_g = sum(p[1] for p in filtered_pixels) // len(filtered_pixels)
        avg_b = sum(p[2] for p in filtered_pixels) // len(filtered_pixels)
    else:
        avg_r = sum(p[0] for p in pixels) // len(pixels)
        avg_g = sum(p[1] for p in pixels) // len(pixels)
        avg_b = sum(p[2] for p in pixels) // len(pixels)

    print(f"\n--- AVERAGE COLOR (filtered) ---")
    print(f"RGB: ({avg_r}, {avg_g}, {avg_b})")
    print(f"HEX: {rgb_to_hex(avg_r, avg_g, avg_b)}")
    h, s, l = rgb_to_hsl(avg_r, avg_g, avg_b)
    print(f"HSL: H:{h} S:{s}% L:{l}%")

    # Find closest named color
    color_name, distance = get_color_name(avg_r, avg_g, avg_b)
    print(f"\n--- CLOSEST NAMED COLOR ---")
    print(f"Name: {color_name} (distance: {distance:.1f})")

    # Determine hue name
    if 150 <= h < 180:
        hue_name = "teal / cyan-green"
    elif 120 <= h < 150:
        hue_name = "green"
    elif 180 <= h < 210:
        hue_name = "cyan / teal-blue"
    else:
        hue_name = f"hue-{h}"

    # Saturation description
    if s < 20:
        sat_desc = "grayish / desaturated"
    elif s < 40:
        sat_desc = "muted / soft"
    elif s < 60:
        sat_desc = "moderate"
    else:
        sat_desc = "vivid / saturated"

    # Lightness description
    if l < 30:
        light_desc = "dark"
    elif l < 50:
        light_desc = "medium-dark"
    elif l < 70:
        light_desc = "medium"
    else:
        light_desc = "light"

    print(f"\n{'='*60}")
    print("AI PROMPT COLOR DESCRIPTIONS")
    print(f"{'='*60}")

    descriptions = [
        f"{color_name}",
        f"{light_desc} {sat_desc} {hue_name}",
        f"teal green with hex {rgb_to_hex(avg_r, avg_g, avg_b)}",
        f"muted teal similar to {color_name}, RGB({avg_r},{avg_g},{avg_b})",
    ]

    for i, desc in enumerate(descriptions, 1):
        print(f"{i}. {desc}")

    print(f"\n{'='*60}")
    print("RECOMMENDED PROMPTS FOR SUIT GENERATION")
    print(f"{'='*60}")

    prompts = [
        f"wearing a 3-piece slim fit suit in {color_name} color (hex {rgb_to_hex(avg_r, avg_g, avg_b)})",
        f"suit color: exactly {rgb_to_hex(avg_r, avg_g, avg_b)}, a {light_desc} {hue_name} tone",
        f"the suit fabric is {color_name}, a {sat_desc} teal-green shade",
    ]

    for i, p in enumerate(prompts, 1):
        print(f"{i}. {p}")

    print(f"\n{'='*60}")
    print("COLOR CODES FOR DIFFERENT PLATFORMS")
    print(f"{'='*60}")

    print(f"\n[RECRAFT V3]")
    print(f'colors: [{{"r": {avg_r}, "g": {avg_g}, "b": {avg_b}}}]')

    print(f"\n[IDEOGRAM V3 - style_image supported]")
    print(f"Can use fabric image directly as style reference!")

    print(f"\n[FLUX + ControlNet]")
    print(f"Use IP-Adapter with fabric image for color/texture transfer")

    print(f"\n[DALL-E 3 / ChatGPT]")
    print(f"Describe as: '{color_name} fabric, exact hex {rgb_to_hex(avg_r, avg_g, avg_b)}'")

    print(f"\n[MIDJOURNEY]")
    print(f"--sref [upload fabric image URL] --sw 100")
    print(f"Or describe: '{color_name}', {light_desc} {hue_name}")

    return {
        "rgb": (avg_r, avg_g, avg_b),
        "hex": rgb_to_hex(avg_r, avg_g, avg_b),
        "hsl": (h, s, l),
        "name": color_name,
        "hue": hue_name,
        "saturation": sat_desc,
        "lightness": light_desc
    }

if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    result = analyze_fabric(fabric_path)

    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Fabric V2535 Color:")
    print(f"  HEX: {result['hex']}")
    print(f"  RGB: {result['rgb']}")
    print(f"  Name: {result['name']}")
    print(f"  Description: {result['lightness']} {result['saturation']} {result['hue']}")
