"""
Color Transfer - Apply fabric swatch color to generated suit image.
Single-pass Reinhard LAB transfer with skin protection.
"""

import io
import requests
import numpy as np
from PIL import Image
from typing import Optional


def transfer_color(source_url: str, target_url: str) -> Optional[bytes]:
    """
    Apply fabric color onto generated suit image.
    Single-pass Reinhard transfer in LAB space with skin/white protection.
    """
    try:
        source_img = _download_image(source_url)
        target_img = _download_image(target_url)

        # Extract fabric color from center of swatch
        src_arr = np.array(source_img)
        h, w = src_arr.shape[:2]
        margin = int(min(h, w) * 0.2)
        center = src_arr[margin:h - margin, margin:w - margin]
        pixels = center.reshape(-1, 3).astype(float)
        brightness = pixels.mean(axis=1)
        valid = (brightness > 20) & (brightness < 240)
        if valid.sum() > 100:
            pixels = pixels[valid]
        fabric_rgb = pixels.mean(axis=0)
        print(f"[color_transfer] Fabric RGB: ({fabric_rgb[0]:.0f},{fabric_rgb[1]:.0f},{fabric_rgb[2]:.0f})")

        result = _recolor(target_img, fabric_rgb)

        buf = io.BytesIO()
        result.save(buf, format='PNG')
        return buf.getvalue()

    except Exception as e:
        print(f"[color_transfer] Error: {e}")
        return None


def _download_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert('RGB')


def _recolor(target: Image.Image, fabric_rgb: np.ndarray) -> Image.Image:
    """
    Reinhard LAB transfer: shift target's color channels toward fabric color.
    Skin and pure white pixels are protected.
    """
    tgt_arr = np.array(target, dtype=np.float64)
    tgt_lab = _rgb_to_lab(tgt_arr)

    # Fabric in LAB
    fab_lab = _rgb_to_lab(fabric_rgb.reshape(1, 1, 3))
    fab_L, fab_a, fab_b = fab_lab[0, 0, 0], fab_lab[0, 0, 1], fab_lab[0, 0, 2]

    # Build protection mask (0 = protected, 1 = apply correction)
    r, g, b = tgt_arr[:, :, 0], tgt_arr[:, :, 1], tgt_arr[:, :, 2]
    bright = (r + g + b) / 3.0

    # Protect skin (warm, R-dominant)
    is_skin = (r > 150) & (r > g + 15) & ((r - b) > 50)
    # Protect pure white (shirt, background)
    is_white = (bright > 230)

    strength = np.ones_like(bright)
    strength[is_skin] = 0.05
    strength[is_white] = 0.05

    # Current image LAB stats (non-protected areas only)
    mask = strength > 0.5
    if mask.sum() < 100:
        mask = np.ones_like(strength, dtype=bool)

    tgt_L_mean = tgt_lab[:, :, 0][mask].mean()
    tgt_a_mean = tgt_lab[:, :, 1][mask].mean()
    tgt_b_mean = tgt_lab[:, :, 2][mask].mean()
    tgt_L_std = max(tgt_lab[:, :, 0][mask].std(), 0.1)
    tgt_a_std = max(tgt_lab[:, :, 1][mask].std(), 0.1)
    tgt_b_std = max(tgt_lab[:, :, 2][mask].std(), 0.1)

    print(f"[color_transfer] Image LAB mean: L={tgt_L_mean:.1f} a={tgt_a_mean:.1f} b={tgt_b_mean:.1f}")
    print(f"[color_transfer] Fabric LAB:     L={fab_L:.1f} a={fab_a:.1f} b={fab_b:.1f}")

    result = tgt_lab.copy()

    # a/b channels: shift mean toward fabric (85% strength)
    for ch, fab_val, tgt_mean in [(1, fab_a, tgt_a_mean), (2, fab_b, tgt_b_mean)]:
        delta = fab_val - tgt_mean
        result[:, :, ch] = tgt_lab[:, :, ch] + delta * 0.85 * strength

    # L channel: shift toward fabric brightness (50% strength, preserve structure)
    delta_L = fab_L - tgt_L_mean
    result[:, :, 0] = tgt_lab[:, :, 0] + delta_L * 0.50 * strength

    # Clip
    result[:, :, 0] = np.clip(result[:, :, 0], 0, 100)
    result[:, :, 1] = np.clip(result[:, :, 1], -128, 127)
    result[:, :, 2] = np.clip(result[:, :, 2], -128, 127)

    rgb = _lab_to_rgb(result)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    rgb_norm = rgb / 255.0
    mask = rgb_norm > 0.04045
    rgb_linear = np.where(mask, ((rgb_norm + 0.055) / 1.055) ** 2.4, rgb_norm / 12.92)

    r, g, b = rgb_linear[..., 0], rgb_linear[..., 1], rgb_linear[..., 2]
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    x /= 0.95047
    z /= 1.08883

    def f(t):
        return np.where(t > 0.008856, t ** (1 / 3), (903.3 * t + 16) / 116)

    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_ch = 200 * (fy - fz)
    return np.stack([L, a, b_ch], axis=-1)


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx = a / 500 + fy
    fz = fy - b / 200

    def f_inv(t):
        t3 = t ** 3
        return np.where(t3 > 0.008856, t3, (116 * t - 16) / 903.3)

    x = f_inv(fx) * 0.95047
    y = f_inv(fy)
    z = f_inv(fz) * 1.08883

    r_lin = x * 3.2404542 + y * -1.5371385 + z * -0.4985314
    g_lin = x * -0.9692660 + y * 1.8760108 + z * 0.0415560
    b_lin = x * 0.0556434 + y * -0.2040259 + z * 1.0572252

    def gamma(c):
        return np.where(c > 0.0031308, 1.055 * (np.maximum(c, 0) ** (1 / 2.4)) - 0.055, 12.92 * c)

    return np.stack([gamma(r_lin), gamma(g_lin), gamma(b_lin)], axis=-1) * 255
