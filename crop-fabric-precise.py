"""
Precise fabric crop - only the fabric texture, no edges
"""
from PIL import Image
from pathlib import Path
import colorsys

def crop_precise(image_path: str, output_path: str):
    """Crop only the pure fabric area"""
    img = Image.open(image_path)
    width, height = img.size
    print(f"Original: {width}x{height}")

    # Very precise crop - just the center fabric area
    # Avoid: left blue edge, right zigzag, bottom label, top edge
    left = int(width * 0.45)   # Further right to avoid blue
    right = int(width * 0.80)  # Before zigzag edge
    top = int(height * 0.20)   # Below top edge
    bottom = int(height * 0.55) # Well above label

    cropped = img.crop((left, top, right, bottom))
    cropped.save(output_path, quality=95)

    print(f"Cropped: {cropped.size}")
    print(f"Saved: {output_path}")

    return cropped

def analyze_precise(img):
    """Analyze color from precise crop"""
    img_rgb = img.convert('RGB')
    pixels = list(img_rgb.getdata())

    # Simple average
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)

    hex_c = f"#{r:02x}{g:02x}{b:02x}"
    h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)

    print(f"\n=== PRECISE COLOR ===")
    print(f"RGB: ({r}, {g}, {b})")
    print(f"HEX: {hex_c}")
    print(f"HSL: H:{int(h*360)} S:{int(s*100)}% L:{int(l*100)}%")

    return {"rgb": (r,g,b), "hex": hex_c}

if __name__ == "__main__":
    fabric_path = r"C:\Users\nurul\Downloads\NEW.1 Super 100s\V2535.jpg"
    output_dir = Path(__file__).parent / "output" / "flux-attempts"

    cropped_path = str(output_dir / "v2535_precise_crop.jpg")
    cropped_img = crop_precise(fabric_path, cropped_path)
    color = analyze_precise(cropped_img)

    print(f"\n=== USE THIS COLOR ===")
    print(f"HEX: {color['hex']}")
    print(f"RGB: {color['rgb']}")
