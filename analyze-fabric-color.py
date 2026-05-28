"""
Fabric Color Analyzer - Extract exact colors from fabric swatch
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
    # Common color references
    colors = {
        "Teal": (0, 128, 128),
        "Cyan": (0, 255, 255),
        "Turquoise": (64, 224, 208),
        "Aquamarine": (127, 255, 212),
        "Sea Green": (46, 139, 87),
        "Medium Sea Green": (60, 179, 113),
        "Light Sea Green": (32, 178, 170),
        "Dark Cyan": (0, 139, 139),
        "Cadet Blue": (95, 158, 160),
        "Steel Blue": (70, 130, 180),
        "Slate Gray": (112, 128, 144),
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
    """Analyze fabric image and extract dominant colors"""
    print(f"\n{'='*60}")
    print(f"FABRIC COLOR ANALYSIS: {Path(image_path).name}")
    print(f"{'='*60}")

    img = Image.open(image_path)
    img = img.convert('RGB')

    width, height = img.size
    print(f"Image size: {width}x{height}")

    # Sample from center area (avoid edges and label)
    # The fabric label is in bottom right, so sample from center-left
    center_x = width // 3
    center_y = height // 2
    sample_size = min(width, height) // 4

    left = center_x - sample_size
    top = center_y - sample_size
    right = center_x + sample_size
    bottom = center_y + sample_size

    # Crop to fabric area
    fabric_area = img.crop((left, top, right, bottom))

    # Get all pixels
    pixels = list(fabric_area.getdata())

    # Count colors (quantize to reduce noise)
    def quantize(color, step=8):
        return tuple((c // step) * step for c in color)

    quantized = [quantize(p) for p in pixels]
    color_counts = Counter(quantized)

    # Get top colors
    top_colors = color_counts.most_common(10)

    print(f"\n--- TOP 10 DOMINANT COLORS ---")
    print(f"{'Rank':<6}{'RGB':<20}{'HEX':<10}{'HSL':<20}{'Count':<10}{'%':<8}")
    print("-" * 74)

    total_pixels = len(pixels)
    dominant_rgb = None

    for i, (color, count) in enumerate(top_colors, 1):
        r, g, b = color
        hex_color = rgb_to_hex(r, g, b)
        hsl = rgb_to_hsl(r, g, b)
        pct = (count / total_pixels) * 100

        if i == 1:
            dominant_rgb = (r, g, b)

        print(f"{i:<6}({r:3},{g:3},{b:3}){'':<6}{hex_color:<10}H:{hsl[0]:3} S:{hsl[1]:2}% L:{hsl[2]:2}%{'':<3}{count:<10}{pct:.1f}%")

    # Calculate average color
    avg_r = sum(p[0] for p in pixels) // len(pixels)
    avg_g = sum(p[1] for p in pixels) // len(pixels)
    avg_b = sum(p[2] for p in pixels) // len(pixels)

    print(f"\n--- AVERAGE COLOR ---")
    print(f"RGB: ({avg_r}, {avg_g}, {avg_b})")
    print(f"HEX: {rgb_to_hex(avg_r, avg_g, avg_b)}")
    print(f"HSL: H:{rgb_to_hsl(avg_r, avg_g, avg_b)[0]} S:{rgb_to_hsl(avg_r, avg_g, avg_b)[1]}% L:{rgb_to_hsl(avg_r, avg_g, avg_b)[2]}%")

    # Find closest named color
    color_name, distance = get_color_name(avg_r, avg_g, avg_b)
    print(f"\n--- CLOSEST NAMED COLOR ---")
    print(f"Name: {color_name} (distance: {distance:.1f})")

    # Pantone-style description
    print(f"\n--- COLOR DESCRIPTION FOR AI PROMPTS ---")
    h, s, l = rgb_to_hsl(avg_r, avg_g, avg_b)

    # Determine hue name
    if h < 30:
        hue_name = "red-orange"
    elif h < 60:
        hue_name = "orange-yellow"
    elif h < 90:
        hue_name = "yellow-green"
    elif h < 150:
        hue_name = "green"
    elif h < 180:
        hue_name = "cyan-green"
    elif h < 210:
        hue_name = "cyan"
    elif h < 240:
        hue_name = "blue"
    elif h < 270:
        hue_name = "blue-purple"
    elif h < 300:
        hue_name = "purple"
    elif h < 330:
        hue_name = "magenta"
    else:
        hue_name = "red"

    # Determine saturation description
    if s < 20:
        sat_desc = "grayish"
    elif s < 40:
        sat_desc = "muted"
    elif s < 60:
        sat_desc = "moderate"
    elif s < 80:
        sat_desc = "vivid"
    else:
        sat_desc = "highly saturated"

    # Determine lightness description
    if l < 20:
        light_desc = "very dark"
    elif l < 40:
        light_desc = "dark"
    elif l < 60:
        light_desc = "medium"
    elif l < 80:
        light_desc = "light"
    else:
        light_desc = "very light"

    description = f"{light_desc} {sat_desc} {hue_name}"
    print(f"Description: {description}")
    print(f"Full prompt color: '{light_desc} {sat_desc} {hue_name} (similar to {color_name})'")

    # Generate specific color codes for different AI tools
    print(f"\n{'='*60}")
    print("COLOR CODES FOR AI IMAGE GENERATORS")
    print(f"{'='*60}")

    print(f"\n[RECRAFT V3 - colors parameter]")
    print(f'colors: [{{"r": {avg_r}, "g": {avg_g}, "b": {avg_b}}}]')

    print(f"\n[MIDJOURNEY - sref + color description]")
    print(f"--sref [fabric_url] OR describe as: {description}, hex {rgb_to_hex(avg_r, avg_g, avg_b)}")

    print(f"\n[IDEOGRAM - color_palette]")
    print(f"Use 'Turquoise' or 'Teal' palette, describe as: {color_name}")

    print(f"\n[FLUX/DALL-E - text description]")
    print(f"'{color_name} colored fabric, {description} tone, hex color {rgb_to_hex(avg_r, avg_g, avg_b)}'")

    print(f"\n[CSS/WEB]")
    print(f"color: {rgb_to_hex(avg_r, avg_g, avg_b)};")
    print(f"color: rgb({avg_r}, {avg_g}, {avg_b});")
    print(f"color: hsl({h}, {s}%, {l}%);")

    return {
        "dominant": dominant_rgb,
        "average": (avg_r, avg_g, avg_b),
        "hex": rgb_to_hex(avg_r, avg_g, avg_b),
        "hsl": (h, s, l),
        "name": color_name,
        "description": description
    }

if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    result = analyze_fabric(fabric_path)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Fabric V2535 exact color: {result['hex']}")
    print(f"RGB: {result['average']}")
    print(f"Best description: {result['description']}")
    print(f"Closest name: {result['name']}")
