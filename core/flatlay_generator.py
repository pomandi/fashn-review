"""
Flat-Lay Suit Generator - Generate a flat-lay suit image with controlled color using Recraft v3.
The generated flat-lay is then fed into FASHN product-to-model for on-model rendering.
"""

import os
import requests
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


FAL_KEY = os.getenv("FAL_KEY") or os.getenv("FASHN_API_KEY")

# Suit style prompt fragments
SUIT_STYLES = {
    "slim-2pc": {
        "name": "Slim Fit 2-Piece",
        "flatlay": "a slim fit two-piece men's suit (jacket and trousers), single-breasted two-button jacket with notch lapel, slim tapered flat-front trousers",
        "onmodel": "slim fit two-piece suit, single-breasted two-button jacket with notch lapel, flat front slim tapered trousers with no break",
    },
    "classic-2pc": {
        "name": "Classic 2-Piece",
        "flatlay": "a classic fit two-piece men's suit (jacket and trousers), single-breasted two-button jacket with notch lapel, straight-leg flat-front trousers",
        "onmodel": "classic fit two-piece suit, single-breasted two-button jacket with notch lapel, flat front straight leg trousers with plain hem, double side vents",
    },
    "modern-2pc-peak": {
        "name": "Modern Peak Lapel",
        "flatlay": "a modern fit two-piece men's suit (jacket and trousers), single-breasted two-button jacket with peak lapel, straight-leg trousers",
        "onmodel": "modern fit two-piece suit, single-breasted two-button jacket with peak lapel, flat front straight leg trousers, jetted pockets, double side vents",
    },
    "slim-3pc": {
        "name": "Slim 3-Piece",
        "flatlay": "a slim fit three-piece men's suit (jacket, five-button V-neck waistcoat, and trousers), single-breasted two-button jacket with peak lapel, slim tapered trousers",
        "onmodel": "slim fit three-piece suit with matching five-button V-neck waistcoat, single-breasted two-button jacket with peak lapel, flat front slim tapered trousers",
    },
    "classic-3pc": {
        "name": "Classic 3-Piece",
        "flatlay": "a classic fit three-piece men's suit (jacket, five-button V-neck waistcoat, and trousers), single-breasted two-button jacket with notch lapel, straight-leg trousers",
        "onmodel": "classic fit three-piece suit with matching five-button V-neck waistcoat, single-breasted two-button jacket with notch lapel, flat front straight leg trousers, double side vents",
    },
    "db-6btn": {
        "name": "Double-Breasted 6-Button",
        "flatlay": "a modern fit double-breasted six-button men's suit (jacket and trousers), wide peak lapel, straight-leg trousers",
        "onmodel": "modern fit double-breasted six-button (2x3) suit, wide peak lapel, flat front straight leg trousers, jetted pockets",
    },
    "db-4btn": {
        "name": "Double-Breasted 4-Button",
        "flatlay": "a slim fit double-breasted four-button men's suit (jacket and trousers), peak lapel, slim tapered trousers",
        "onmodel": "slim fit double-breasted four-button (2x2) suit, peak lapel, flat front slim tapered trousers, jetted pockets",
    },
    "tuxedo-shawl": {
        "name": "Tuxedo Shawl",
        "flatlay": "a slim fit men's tuxedo (jacket and trousers), single-breasted one-button jacket with satin shawl lapel, satin side-striped trousers",
        "onmodel": "slim fit tuxedo, single-breasted one-button jacket with satin-faced shawl lapel, satin covered buttons, jetted pockets, flat front slim trousers with satin side stripe",
    },
    "tuxedo-peak": {
        "name": "Tuxedo Peak",
        "flatlay": "a slim fit men's tuxedo (jacket and trousers), single-breasted one-button jacket with satin peak lapel, satin side-striped trousers",
        "onmodel": "slim fit tuxedo, single-breasted one-button jacket with satin-faced peak lapel, satin covered buttons, jetted pockets, flat front slim trousers with satin side stripe",
    },
    "3pc-db-vest": {
        "name": "3-Piece + DB Vest",
        "flatlay": "a modern fit three-piece men's suit (jacket, double-breasted peak-lapel waistcoat, and trousers), single-breasted two-button jacket with peak lapel",
        "onmodel": "modern fit three-piece suit with double-breasted peak lapel waistcoat, single-breasted two-button jacket with peak lapel, flat front straight leg trousers",
    },
    "3pc-shawl-vest": {
        "name": "3-Piece + Shawl Vest",
        "flatlay": "a slim fit three-piece men's suit (jacket, shawl-collar waistcoat, and trousers), single-breasted two-button jacket with peak lapel, slim trousers",
        "onmodel": "slim fit three-piece suit with shawl collar waistcoat, single-breasted two-button jacket with peak lapel, flat front slim tapered trousers",
    },
}


def generate_flatlay(color_info: Dict, suit_style: str = "slim-2pc") -> Optional[str]:
    """
    Generate a flat-lay suit image with Recraft v3 using exact color control.

    Args:
        color_info: Output from fabric_analyzer (must have 'rgb', 'hex', 'color_name', 'description')
        suit_style: Key from SUIT_STYLES

    Returns:
        URL of generated flat-lay image, or None on failure
    """
    if not FAL_KEY:
        raise ValueError("FAL_KEY / FASHN_API_KEY not set")

    style = SUIT_STYLES.get(suit_style, SUIT_STYLES["slim-2pc"])
    r, g, b = color_info["rgb"]
    color_name = color_info.get("color_name", "")
    hex_color = color_info.get("hex", "")
    description = color_info.get("description", "")

    prompt = (
        f"Professional product photography, top-down flat-lay of {style['flatlay']}. "
        f"The suit is made of {color_name} colored fine wool fabric ({hex_color}), {description}. "
        f"Suit neatly arranged on a clean white surface. "
        f"All pieces matching in color and fabric. "
        f"Crisp, sharp studio lighting, no shadows, catalog-quality product photo."
    )

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "style": "realistic_image",
        "colors": [{"r": r, "g": g, "b": b}],
        "output_format": "png",
    }

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }

    print(f"[flatlay] Generating {style['name']} in {color_name} ({hex_color})...")

    resp = requests.post(
        "https://fal.run/fal-ai/recraft/v3/text-to-image",
        headers=headers,
        json=payload,
        timeout=180,
    )

    if resp.status_code == 200:
        data = resp.json()
        images = data.get("images", [])
        if images:
            url = images[0].get("url")
            print(f"[flatlay] Success: {url}")
            return url

    print(f"[flatlay] Recraft failed ({resp.status_code}), trying Flux Pro fallback...")
    return _flux_fallback(color_info, style)


def _flux_fallback(color_info: Dict, style: Dict) -> Optional[str]:
    """Fallback: use Flux Pro with detailed color description in prompt"""
    r, g, b = color_info["rgb"]
    hex_color = color_info["hex"]
    color_name = color_info.get("color_name", "")

    prompt = (
        f"Professional product photography, top-down flat-lay of {style['flatlay']}. "
        f"IMPORTANT: The suit color is EXACTLY {hex_color} (RGB {r},{g},{b}), "
        f"a {color_name} shade. Not brighter, not darker, EXACTLY this color. "
        f"Fine wool fabric with subtle texture. "
        f"Suit neatly arranged on a clean white surface. "
        f"Crisp studio lighting, no shadows, catalog-quality product photo."
    )

    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 28,
        "guidance_scale": 4.0,
        "num_images": 1,
        "output_format": "png",
    }

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        "https://fal.run/fal-ai/flux-pro/v1.1",
        headers=headers,
        json=payload,
        timeout=180,
    )

    if resp.status_code == 200:
        data = resp.json()
        images = data.get("images", [])
        if images:
            url = images[0].get("url")
            print(f"[flatlay-flux] Success: {url}")
            return url

    print(f"[flatlay-flux] Also failed ({resp.status_code}): {resp.text[:200]}")
    return None


def get_onmodel_prompt(suit_style: str = "slim-2pc") -> str:
    """Get the on-model prompt fragment for FASHN product-to-model"""
    style = SUIT_STYLES.get(suit_style, SUIT_STYLES["slim-2pc"])
    return style["onmodel"]
