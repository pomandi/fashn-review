"""
Imagen 3 Generator - Generate suit images using Google Vertex AI Imagen 3.
Two modes: flat-lay product photo + lifestyle editorial photo.
"""

import os
import base64
import requests
from typing import Optional, List, Dict
from google.oauth2 import service_account
from google.auth.transport.requests import Request

CREDS_PATH = "/home/claude/projects/sale-v2/.claude/google_credentials.json"
PROJECT = "papyon-1577961349408"
LOCATION = "us-central1"
MODEL = "imagen-3.0-generate-002"

# ── Model Types ──
MODELS = {
    "dutch-blond": "tall elegant blond Dutch man, age 28-32, sharp symmetrical features, clean-shaven, athletic build",
    "italian-dark": "distinguished Italian man, age 30-35, dark hair, olive skin, strong jawline, Mediterranean features",
    "classic-british": "refined British gentleman, age 35-40, light brown hair, fair skin, aristocratic features",
    "young-modern": "young stylish man, age 24-28, modern groomed look, confident expression, model physique",
}

# ── Photography Styles (randomly selected if no specific preset) ──
PHOTOGRAPHER_STYLES = [
    {
        "name": "Mario Testino",
        "style": "Shot in the style of Mario Testino. Warm golden tones, glamorous natural light, "
                 "effortless Italian elegance, slightly overexposed highlights, sensual yet refined, "
                 "intimate luxury atmosphere"
    },
    {
        "name": "Peter Lindbergh",
        "style": "Shot in the style of Peter Lindbergh. Raw, honest, emotional black-and-white-inspired "
                 "tones converted to muted color, minimal retouching, strong character, "
                 "documentary fashion feel, wind-blown natural energy"
    },
    {
        "name": "Steven Meisel",
        "style": "Shot in the style of Steven Meisel. Hyper-polished editorial perfection, "
                 "dramatic studio-quality lighting, rich saturated colors, bold composition, "
                 "magazine-cover precision, powerful masculine energy"
    },
    {
        "name": "Patrick Demarchelier",
        "style": "Shot in the style of Patrick Demarchelier. Clean, classic, timeless elegance, "
                 "soft diffused natural light, neutral backdrop, effortless sophistication, "
                 "the definitive menswear catalog aesthetic"
    },
    {
        "name": "Helmut Newton",
        "style": "Shot in the style of Helmut Newton. Dramatic high-contrast lighting, "
                 "bold architectural composition, powerful masculine stance, noir atmosphere, "
                 "sharp shadows, provocative confidence"
    },
    {
        "name": "Annie Leibovitz",
        "style": "Shot in the style of Annie Leibovitz. Cinematic storytelling composition, "
                 "rich painterly lighting, environmental portrait in grand setting, "
                 "narrative depth, museum-quality framing"
    },
    {
        "name": "Bruce Weber",
        "style": "Shot in the style of Bruce Weber. All-American masculine energy, "
                 "warm sun-drenched outdoor light, athletic confidence, golden hour glow, "
                 "relaxed yet powerful, Ralph Lauren campaign feel"
    },
    {
        "name": "Inez & Vinoodh",
        "style": "Shot in the style of Inez and Vinoodh. Ultra-modern, hyper-clean aesthetic, "
                 "stark minimalist composition, precise geometric framing, "
                 "futuristic luxury, sharp focus with dreamlike quality"
    },
    {
        "name": "Paolo Roversi",
        "style": "Shot in the style of Paolo Roversi. Ethereal, painterly soft focus, "
                 "muted romantic tones, Polaroid-like dreamy quality, gentle diffused light, "
                 "mysterious and poetic atmosphere"
    },
    {
        "name": "Lachlan Bailey",
        "style": "Shot in the style of Lachlan Bailey. Contemporary menswear editorial, "
                 "natural daylight, relaxed urban sophistication, authentic modern masculinity, "
                 "clean warm tones, effortless cool"
    },
]

# ── Lifestyle Prompt Presets ──
LIFESTYLE_PRESETS = {
    "milan-street": {
        "name": "Milan Fashion District",
        "prompt": "walking confidently on an elegant Milan cobblestone street, warm golden afternoon sunlight, beautiful Italian architecture with ornate facades, soft bokeh background, Mediterranean atmosphere",
    },
    "wedding-groom": {
        "name": "Wedding / Groom",
        "prompt": "standing in a beautiful garden venue with white flowers, soft romantic lighting, wedding ceremony atmosphere, elegant and emotional, blurred guests in background",
    },
    "business-office": {
        "name": "Business Executive",
        "prompt": "standing in a modern luxury office with floor-to-ceiling windows overlooking a city skyline, clean minimal interior, confident executive pose, natural daylight",
    },
    "evening-gala": {
        "name": "Evening Gala",
        "prompt": "at an elegant black-tie gala event, grand ballroom with crystal chandeliers, dramatic warm lighting, sophisticated luxury atmosphere",
    },
    "coastal-summer": {
        "name": "Coastal Summer",
        "prompt": "standing on a Mediterranean terrace overlooking the sea, white architecture, bright natural sunlight, blue sky, relaxed yet elegant summer atmosphere",
    },
    "classic-studio": {
        "name": "Classic Studio",
        "prompt": "in a professional photography studio, clean light gray background, perfect studio lighting with soft shadows, high-end fashion catalog style",
    },
    "autumn-city": {
        "name": "Autumn City",
        "prompt": "walking through a European city park in autumn, golden fallen leaves, warm afternoon light filtering through trees, rich autumnal atmosphere",
    },
    "hotel-lobby": {
        "name": "Luxury Hotel Lobby",
        "prompt": "standing in a grand luxury hotel lobby with marble floors and columns, warm ambient lighting, Art Deco details, sophisticated elegance",
    },
    "rooftop-sunset": {
        "name": "Rooftop Sunset",
        "prompt": "on a modern rooftop terrace at golden hour, city skyline in background, dramatic sunset colors, contemporary urban luxury atmosphere",
    },
    "vintage-car": {
        "name": "Vintage Gentleman",
        "prompt": "leaning against a classic vintage car (1960s), elegant country estate driveway, warm golden light, timeless gentleman style, cinematic composition",
    },
}

# ── Suit Style Descriptions ──
SUIT_STYLES_IMAGEN = {
    "slim-2pc": "slim fit two-piece suit, single-breasted two-button jacket with notch lapel, slim tapered flat-front trousers",
    "classic-2pc": "classic fit two-piece suit, single-breasted two-button jacket with notch lapel, straight-leg flat-front trousers",
    "slim-3pc": "slim fit three-piece suit with matching five-button V-neck waistcoat, single-breasted two-button jacket with peak lapel, slim tapered trousers",
    "classic-3pc": "classic fit three-piece suit with matching waistcoat, single-breasted two-button jacket with notch lapel, straight-leg trousers",
    "db-6btn": "double-breasted six-button suit, wide peak lapel, straight-leg trousers",
    "tuxedo-shawl": "tuxedo with satin-faced shawl lapel, one-button jacket, satin-striped slim trousers",
    "tuxedo-peak": "tuxedo with satin-faced peak lapel, one-button jacket, satin-striped slim trousers",
}


def _get_credentials():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return creds


def _call_imagen(prompt: str, count: int = 1, aspect: str = "3:4", allow_person: bool = True) -> List[bytes]:
    """Call Imagen 3 API and return list of image bytes."""
    creds = _get_credentials()
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/{MODEL}:predict"

    resp = requests.post(url, headers={
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }, json={
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": count,
            "aspectRatio": aspect,
            "personGeneration": "allow_all" if allow_person else "dont_allow",
            "safetySetting": "block_few",
        },
    }, timeout=120)

    if resp.status_code != 200:
        raise Exception(f"Imagen 3 error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    images = []
    for pred in data.get("predictions", []):
        images.append(base64.b64decode(pred["bytesBase64Encoded"]))
    return images


def generate_flatlay(color_info: Dict, suit_style: str = "slim-2pc") -> Optional[bytes]:
    """
    Generate a flat-lay suit image with Imagen 3.
    """
    r, g, b = color_info["rgb"]
    hex_c = color_info["hex"]
    name = color_info["color_name"]
    style = SUIT_STYLES_IMAGEN.get(suit_style, SUIT_STYLES_IMAGEN["slim-2pc"])

    prompt = (
        f"Top-down flat-lay product photo of a {name} colored men's {style} "
        f"on a white surface. The suit color is {hex_c}. "
        f"Matching jacket and trousers in the same {name} wool fabric. "
        f"Studio lighting, catalog photo. No person."
    )

    print(f"[imagen] Flat-lay: {name} ({hex_c}) {suit_style}")
    images = _call_imagen(prompt, count=1, aspect="3:4", allow_person=False)
    return images[0] if images else None


def generate_lifestyle(color_info: Dict, suit_style: str = "slim-2pc",
                       model_type: str = "dutch-blond", preset: str = "milan-street",
                       custom_scene: str = "", count: int = 4) -> List[bytes]:
    """
    Generate lifestyle editorial photos with Imagen 3.
    Automatically selects a random photographer style for unique results.

    Args:
        color_info: from fabric_analyzer
        suit_style: suit style key
        model_type: model appearance key
        preset: lifestyle preset key
        custom_scene: custom scene description (overrides preset)
        count: number of images to generate (1-4)

    Returns:
        List of PNG image bytes
    """
    import random

    r, g, b = color_info["rgb"]
    hex_c = color_info["hex"]
    name = color_info["color_name"]
    desc = color_info.get("description", "")
    style = SUIT_STYLES_IMAGEN.get(suit_style, SUIT_STYLES_IMAGEN["slim-2pc"])
    model_desc = MODELS.get(model_type, MODELS["dutch-blond"])

    if custom_scene:
        scene = custom_scene
    else:
        scene = LIFESTYLE_PRESETS.get(preset, LIFESTYLE_PRESETS["milan-street"])["prompt"]

    # Random photographer style
    photographer = random.choice(PHOTOGRAPHER_STYLES)

    prompt = (
        f"A {model_desc} wearing a {name} colored {style}, white shirt. "
        f"Suit color: {hex_c}. "
        f"{scene}. "
        f"{photographer['style']}"
    )

    print(f"[imagen] Lifestyle: {model_type} / {preset} / {name} ({hex_c}) / {photographer['name']}")
    print(f"[imagen] Prompt ({len(prompt)} chars): {prompt[:120]}...")
    return _call_imagen(prompt, count=count, aspect="3:4", allow_person=True)


def get_presets() -> Dict:
    """Return available presets for UI."""
    return {
        "models": {k: v.split(",")[0] for k, v in MODELS.items()},
        "scenes": {k: v["name"] for k, v in LIFESTYLE_PRESETS.items()},
        "styles": {k: v.split(",")[0] for k, v in SUIT_STYLES_IMAGEN.items()},
        "photographers": [p["name"] for p in PHOTOGRAPHER_STYLES],
    }
