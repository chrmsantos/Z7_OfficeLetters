"""Generate the Z7 OfficeLetters application icon.

Renders a multi-resolution ``icon.ico`` file using only Pillow.

Visual concept (v2 — redesign):
- Rounded background with simulated radial gradient (navy → indigo).
- Inner frame with subtle highlight in the upper corner.
- Elevated paper sheet with diffused shadow and detailed folded corner.
- "Z7" monogram on the paper (brand identity).
- Stylised text lines below the monogram.
- Redesigned fountain pen: bicolour body, faceted nib, glass-reflection highlight.

Usage::

    python scripts/generate_icon.py

Requires ``pillow``::

    pip install pillow
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# ── Colour palette ─────────────────────────────────────────────────────────
BG_OUTER: tuple[int, int, int, int] = (12,  14,  30, 255)
BG_INNER: tuple[int, int, int, int] = (28,  34,  72, 255)
BG_SHINE: tuple[int, int, int, int] = (255, 255, 255, 18)
BORDER_C: tuple[int, int, int, int] = (60,  70, 130, 160)

PAPER_W:    tuple[int, int, int, int] = (228, 234, 252, 255)
PAPER_SHD:  tuple[int, int, int, int] = (0,   0,   0,   70)
PAPER_FOLD: tuple[int, int, int, int] = (180, 190, 225, 255)
PAPER_EDGE: tuple[int, int, int, int] = (155, 165, 200, 255)

MONO_COLOR: tuple[int, int, int, int] = (40,  80, 200, 255)
LINE_C:     tuple[int, int, int, int] = (140, 155, 200, 120)

PEN_NIB_L:  tuple[int, int, int, int] = (250, 215,  80, 255)
PEN_NIB_D:  tuple[int, int, int, int] = (160, 118,  20, 220)
PEN_INK:    tuple[int, int, int, int] = (30,  30,   90, 255)
PEN_GRIP:   tuple[int, int, int, int] = (55,  62,   90, 255)
PEN_BODY_A: tuple[int, int, int, int] = (30,  60,  160, 255)
PEN_BODY_B: tuple[int, int, int, int] = (55, 100,  220, 255)
PEN_BODY_H: tuple[int, int, int, int] = (180, 210, 255, 110)
PEN_CAP:    tuple[int, int, int, int] = (16,  28,   80, 255)
PEN_CAP_H:  tuple[int, int, int, int] = (80, 110,  200,  90)
PEN_RING:   tuple[int, int, int, int] = (215, 185,  55, 255)
PEN_SHADOW: tuple[int, int, int, int] = (0,   0,    0,   80)


# ── Drawing helpers ─────────────────────────────────────────────────────────

def _rr(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, ...] | None = None,
    outline: tuple[int, ...] | None = None,
    width: int = 1,
) -> None:
    """Draw a rounded rectangle, with a fallback for older Pillow versions."""
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        x0, y0, x1, y1 = xy
        r = radius
        draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
        draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
        for ex, ey in [(x0, y0), (x1 - 2 * r, y0), (x0, y1 - 2 * r), (x1 - 2 * r, y1 - 2 * r)]:
            draw.ellipse([ex, ey, ex + 2 * r, ey + 2 * r], fill=fill)


def _sp(pts: list[tuple[float, float]], s: float) -> list[tuple[int, int]]:
    """Scale float ``(x, y)`` tuples to integer pixel coordinates.

    Args:
        pts: List of float coordinate pairs.
        s: Scale factor (``target_size / 256``).

    Returns:
        List of integer pixel coordinate pairs.
    """
    return [(int(x * s + 0.5), int(y * s + 0.5)) for x, y in pts]


def _lerp_color(
    c0: tuple[int, ...],
    c1: tuple[int, ...],
    t: float,
) -> tuple[int, ...]:
    """Linearly interpolate two RGBA colours.

    Args:
        c0: Start colour.
        c1: End colour.
        t: Interpolation factor in [0.0, 1.0].

    Returns:
        Interpolated RGBA tuple.
    """
    return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))


# ── Background ──────────────────────────────────────────────────────────────

def _draw_background(img: Image.Image, size: int) -> None:
    """Fill the image with a simulated radial gradient (centre → edges).

    Args:
        img: Target ``RGBA`` image (modified in-place).
        size: Width/height of the square image in pixels.
    """
    cx, cy = size / 2, size / 2
    max_r = math.hypot(cx, cy)
    px = img.load()
    if px is None:
        return
    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - cx, y - cy)
            t = min(dist / max_r, 1.0)
            c = _lerp_color(BG_INNER, BG_OUTER, t ** 0.7)
            px[x, y] = c  # type: ignore[index]


# ── Main render ─────────────────────────────────────────────────────────────

def draw_frame(size: int) -> Image.Image:
    """Render a single icon frame at the given square pixel size.

    Args:
        size: Target size in pixels (e.g. 256, 128, 64, 48, 32, 16).

    Returns:
        RGBA ``Image`` ready to be saved as an ICO frame.
    """
    s = size / 256.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    d = ImageDraw.Draw(img)

    # Paper shadow
    if size >= 32:
        off = max(2, int(4 * s))
        shd_pts: list[tuple[float, float]] = [
            (48 + off, 30 + off), (180 + off, 30 + off),
            (180 + off, 220 + off), (48 + off, 220 + off),
        ]
        d.polygon(_sp(shd_pts, s), fill=PAPER_SHD)

    # Paper body
    px0, py0 = 48.0, 32.0
    px1, py1 = 178.0, 218.0
    fold = 34.0

    paper_body: list[tuple[float, float]] = [
        (px0, py0), (px1 - fold, py0),
        (px1, py0 + fold), (px1, py1), (px0, py1),
    ]
    d.polygon(_sp(paper_body, s), fill=PAPER_W)

    fold_face: list[tuple[float, float]] = [
        (px1 - fold, py0), (px1, py0 + fold), (px1 - fold, py0 + fold),
    ]
    d.polygon(_sp(fold_face, s), fill=PAPER_FOLD)
    d.line(
        _sp([(px1 - fold, py0), (px1, py0 + fold)], s),
        fill=PAPER_EDGE, width=max(1, int(2 * s)),
    )

    # "Z7" monogram
    if size >= 48:
        zx, zy = 62.0, 52.0
        zw, zh = 36.0, 34.0
        lw_m = max(2, int(4 * s))
        d.line(_sp([(zx, zy), (zx + zw, zy)], s), fill=MONO_COLOR, width=lw_m)
        d.line(_sp([(zx + zw, zy), (zx, zy + zh)], s), fill=MONO_COLOR, width=lw_m)
        d.line(_sp([(zx, zy + zh), (zx + zw, zy + zh)], s), fill=MONO_COLOR, width=lw_m)

        sx, sy = zx + zw + 8.0, zy
        sw, sh = 26.0, 34.0
        d.line(_sp([(sx, sy), (sx + sw, sy)], s), fill=MONO_COLOR, width=lw_m)
        d.line(_sp([(sx + sw, sy), (sx + 6, sy + sh)], s), fill=MONO_COLOR, width=lw_m)
        d.line(
            _sp([(sx + 5, sy + sh * 0.5), (sx + sw - 4, sy + sh * 0.5)], s),
            fill=MONO_COLOR, width=max(1, int(2.5 * s)),
        )

    # Text lines
    if size >= 32:
        lx0, lx1 = px0 + 12, px1 - 8
        lw_t = max(1, int(3 * s))
        y_base = 108.0 if size >= 48 else 90.0
        for i, dy in enumerate([0.0, 22.0, 44.0, 66.0]):
            rx = lx1 if i < 3 else lx0 + (lx1 - lx0) * 0.5
            d.line(_sp([(lx0, y_base + dy), (rx, y_base + dy)], s),
                   fill=LINE_C, width=lw_t)

    # ── Fountain pen ─────────────────────────────────────────────────────────
    NIB_TIP = (66.0, 200.0)
    CAP_END = (196.0, 46.0)

    dxv = CAP_END[0] - NIB_TIP[0]
    dyv = CAP_END[1] - NIB_TIP[1]
    L   = math.hypot(dxv, dyv)

    ux, uy = dxv / L, dyv / L   # pen axis unit vector
    perp_x, perp_y = -uy, ux    # perpendicular (right side)

    def point(t: float, w: float = 0.0) -> tuple[float, float]:
        return (
            NIB_TIP[0] + t * ux + w * perp_x,
            NIB_TIP[1] + t * uy + w * perp_y,
        )

    def quad(t0: float, t1: float, w0: float, w1: float) -> list[tuple[float, float]]:
        return [point(t0, +w0), point(t1, +w1), point(t1, -w1), point(t0, -w0)]

    T_NIB_END  =  28.0
    T_GRIP_END =  56.0
    T_R1_S     =  58.0
    T_R1_E     =  66.0
    T_MID      = (T_R1_E + (L - 20)) / 2
    T_BODY_END = L - 20.0
    T_R2_S     = T_BODY_END + 2.0
    T_R2_E     = T_BODY_END + 10.0
    T_CAP_END  = L

    W_NIB  =  7.0
    W_GRIP =  9.0
    W_BODY = 11.5
    W_CAP  = 12.5
    W_RING = 13.5

    # Pen shadow
    if size >= 32:
        off = max(2, int(3 * s))
        for poly in [
            quad(0,          T_NIB_END,  0,      W_NIB),
            quad(T_NIB_END,  T_GRIP_END, W_GRIP, W_GRIP),
            quad(T_R1_E,     T_BODY_END, W_BODY, W_BODY),
            quad(T_R2_E,     T_CAP_END,  W_CAP,  W_CAP),
        ]:
            d.polygon(
                [(int(x * s + off + 0.5), int(y * s + off + 0.5)) for x, y in poly],
                fill=PEN_SHADOW,
            )

    # Nib faces
    nb_r = point(T_NIB_END, +W_NIB)
    nb_l = point(T_NIB_END, -W_NIB)
    nb_c = point(T_NIB_END, 0.0)
    d.polygon(_sp([NIB_TIP, nb_r, nb_l], s), fill=PEN_NIB_D)
    d.polygon(_sp([NIB_TIP, nb_r, nb_c], s), fill=PEN_NIB_L)

    # Ink dot
    if size >= 48:
        tx, ty = int(NIB_TIP[0] * s + 0.5), int(NIB_TIP[1] * s + 0.5)
        rd = max(2, int(3.5 * s))
        d.ellipse([tx - rd, ty - rd, tx + rd, ty + rd], fill=PEN_INK)

    # Grip
    d.polygon(_sp(quad(T_NIB_END, T_GRIP_END, W_GRIP, W_GRIP), s), fill=PEN_GRIP)

    # Ring 1
    if size >= 32:
        d.polygon(_sp(quad(T_R1_S, T_R1_E, W_RING, W_RING), s), fill=PEN_RING)

    # Bicolour body
    if size >= 64:
        d.polygon(_sp(quad(T_R1_E, T_MID,      W_BODY, W_BODY), s), fill=PEN_BODY_A)
        d.polygon(_sp(quad(T_MID,  T_BODY_END,  W_BODY, W_BODY), s), fill=PEN_BODY_B)
    else:
        d.polygon(_sp(quad(T_R1_E, T_BODY_END, W_BODY, W_BODY), s), fill=PEN_BODY_A)

    # Body glass reflection
    if size >= 48:
        hl_s = point(T_R1_E + 10, -(W_BODY - 4))
        hl_e = point(T_BODY_END - 10, -(W_BODY - 4))
        d.line(_sp([hl_s, hl_e], s), fill=PEN_BODY_H, width=max(1, int(2 * s)))

    # Ring 2
    if size >= 32:
        d.polygon(_sp(quad(T_R2_S, T_R2_E, W_RING, W_RING), s), fill=PEN_RING)

    # Cap
    d.polygon(_sp(quad(T_R2_E, T_CAP_END, W_CAP, W_CAP), s), fill=PEN_CAP)
    cap_c = point(T_CAP_END, 0.0)
    rc = int(W_CAP * s + 0.5)
    ccx, ccy = int(cap_c[0] * s + 0.5), int(cap_c[1] * s + 0.5)
    d.ellipse([ccx - rc, ccy - rc, ccx + rc, ccy + rc], fill=PEN_CAP)

    # Cap reflection
    if size >= 48:
        hl_cs = point(T_R2_E + 6, -(W_CAP - 4))
        hl_ce = point(T_CAP_END - 6, -(W_CAP - 4))
        d.line(_sp([hl_cs, hl_ce], s), fill=PEN_CAP_H, width=max(1, int(2 * s)))

    # Golden clip
    if size >= 48:
        cl_s = point(T_R2_E + 6, -(W_CAP + 1.5))
        cl_e = point(T_CAP_END - 6, -(W_CAP + 1.5))
        d.line(_sp([cl_s, cl_e], s), fill=PEN_RING, width=max(1, int(3 * s)))

    return img


def build_ico(out_path: Path) -> None:
    """Build a multi-resolution ICO file from ``draw_frame``.

    Args:
        out_path: Destination ``.ico`` file path.
    """
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [draw_frame(sz) for sz in sizes]
    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f"OK: {out_path} ({out_path.stat().st_size // 1024} KB, {len(sizes)} sizes)")


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "icon.ico"
    build_ico(out)
