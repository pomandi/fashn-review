"""
Fabric Analyzer - Extract fabric color using Claude Vision AI.
Falls back to algorithmic analysis if AI fails.
"""

import io
import base64
import json
import colorsys
import requests
from PIL import Image
from typing import Dict, Tuple
from anthropic import Anthropic

ANTHROPIC_AUTH_TOKEN = "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"


def _get_client():
    return Anthropic(
        auth_token=ANTHROPIC_AUTH_TOKEN,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


def analyze_from_url(image_url: str) -> Dict:
    """Analyze fabric color — Claude Vision AI primary, algorithmic fallback."""
    try:
        return _analyze_with_claude(image_url)
    except Exception as e:
        print(f"[fabric_analyzer] Claude Vision failed ({e}), using fallback")
        return _analyze_algorithmic(image_url)


def analyze_from_path(image_path: str) -> Dict:
    """Analyze from local file."""
    img = Image.open(image_path).convert('RGB')
    return _analyze_pil(img)


def _analyze_with_claude(image_url: str) -> Dict:
    """Use Claude Vision to identify fabric color — most accurate method."""
    client = _get_client()

    # Download and resize
    img = Image.open(io.BytesIO(requests.get(image_url, timeout=30).content)).convert('RGB')
    img.thumbnail((800, 800))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=120,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': img_b64}},
                {'type': 'text', 'text': (
                    'This is a fabric swatch photo for a men\'s suit. '
                    'What is the exact color of the FABRIC (not the background/table)? '
                    'Reply ONLY with JSON: {"color_name":"...","hex":"#......","rgb":[R,G,B]}. '
                    'Use fashion-industry color names (Cream, Ivory, Navy, Charcoal, '
                    'Petrol Green, Burgundy, Slate Blue, Camel, etc). Be precise.'
                )}
            ]
        }]
    )

    text = msg.content[0].text.strip()
    # Strip markdown code blocks if present
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

    data = json.loads(text)
    r, g, b = data['rgb']
    hex_color = data.get('hex', f'#{r:02x}{g:02x}{b:02x}')
    color_name = data['color_name']

    h, s, l = _rgb_to_hsl(r, g, b)
    desc = _describe_color(h, s, l)

    print(f"[fabric_analyzer] Claude Vision: {color_name} ({hex_color})")

    return {
        "rgb": [r, g, b],
        "hex": hex_color.lower(),
        "hsl": [h, s, l],
        "color_name": color_name,
        "color_distance": 0,
        "description": f"{desc['lightness']} {desc['saturation']} {desc['hue']}",
        "desc_parts": desc,
        "top_colors": [{"rgb": [r, g, b], "hex": hex_color.lower(), "pct": 100.0}],
        "prompt_color": f"{color_name} ({hex_color})",
        "source": "claude_vision",
    }


def _analyze_algorithmic(image_url: str) -> Dict:
    """Fallback: algorithmic analysis using center crop + averaging."""
    img = Image.open(io.BytesIO(requests.get(image_url, timeout=30).content)).convert('RGB')
    return _analyze_pil(img)


def _analyze_pil(img: Image.Image) -> Dict:
    """Simple center-patch analysis as fallback."""
    import numpy as np

    w, h = img.size
    arr = np.array(img)

    # Center 8% patch
    patch_size = max(int(min(w, h) * 0.08), 30)
    cx, cy = w // 2, h // 2
    half = patch_size // 2
    patch = arr[cy - half:cy + half, cx - half:cx + half]
    avg = patch.mean(axis=(0, 1))
    avg_r, avg_g, avg_b = int(avg[0]), int(avg[1]), int(avg[2])

    hex_color = f'#{avg_r:02x}{avg_g:02x}{avg_b:02x}'
    h, s, l = _rgb_to_hsl(avg_r, avg_g, avg_b)
    desc = _describe_color(h, s, l)
    color_name = f"{desc['lightness'].title()} {desc['hue'].title()}"

    return {
        "rgb": [avg_r, avg_g, avg_b],
        "hex": hex_color,
        "hsl": [h, s, l],
        "color_name": color_name,
        "color_distance": 0,
        "description": f"{desc['lightness']} {desc['saturation']} {desc['hue']}",
        "desc_parts": desc,
        "top_colors": [{"rgb": [avg_r, avg_g, avg_b], "hex": hex_color, "pct": 100.0}],
        "prompt_color": f"{color_name} ({hex_color})",
        "source": "algorithmic",
    }


def _rgb_to_hsl(r: int, g: int, b: int) -> Tuple[int, int, int]:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return (int(h * 360), int(s * 100), int(l * 100))


def _describe_color(h: int, s: int, l: int) -> Dict[str, str]:
    if s < 10:
        hue = "neutral gray"
    elif h < 15 or h >= 345:
        hue = "red"
    elif h < 40:
        hue = "orange-brown"
    elif h < 65:
        hue = "yellow-gold"
    elif h < 150:
        hue = "green"
    elif h < 190:
        hue = "teal-cyan"
    elif h < 260:
        hue = "blue"
    elif h < 290:
        hue = "purple"
    else:
        hue = "magenta-pink"

    if s < 15:
        sat = "grayish"
    elif s < 30:
        sat = "muted"
    elif s < 55:
        sat = "moderate"
    else:
        sat = "vivid"

    if l < 15:
        light = "very dark"
    elif l < 30:
        light = "dark"
    elif l < 45:
        light = "medium-dark"
    elif l < 60:
        light = "medium"
    elif l < 75:
        light = "medium-light"
    else:
        light = "light"

    return {"hue": hue, "saturation": sat, "lightness": light}
