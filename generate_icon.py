"""
generate_icon.py — Gera o ícone icon.ico para o Z7 OfficeLetters.

Conceito visual (v2 — redesign):
  - Fundo arredondado com gradiente radial simulado (azul-marinho → índigo)
  - Moldura interna com brilho sutil (highlight no canto superior)
  - Folha de papel elevada com sombra difusa e canto dobrado detalhado
  - Monograma "Z7" no papel (identidade visual da marca)
  - Linhas de texto estilizadas abaixo do monograma
  - Caneta tinteiro remodelada: corpo bicolor, bico facetado, reflexo de vidro

Execute:  python generate_icon.py
Requer:   pip install pillow
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


# ── Paleta ─────────────────────────────────────────────────────────────────
BG_OUTER   = ( 12,  14,  30, 255)   # borda / canto mais escuro do gradiente
BG_INNER   = ( 28,  34,  72, 255)   # centro do gradiente de fundo
BG_SHINE   = (255, 255, 255,  18)   # brilho no canto superior-esquerdo do fundo
BORDER_C   = ( 60,  70, 130, 160)   # borda externa suave

PAPER_W    = (228, 234, 252, 255)   # papel branco-azulado
PAPER_SHD  = (  0,   0,   0,  70)   # sombra do papel
PAPER_FOLD = (180, 190, 225, 255)   # triângulo do canto dobrado
PAPER_EDGE = (155, 165, 200, 255)   # aresta da dobra

MONO_COLOR = ( 40,  80, 200, 255)   # azul do monograma "Z7"
LINE_C     = (140, 155, 200, 120)   # linhas de texto

PEN_NIB_L  = (250, 215,  80, 255)   # bico dourado — face clara
PEN_NIB_D  = (160, 118,  20, 220)   # bico dourado — face escura
PEN_INK    = ( 30,  30,  90, 255)   # ponto de tinta na ponta
PEN_GRIP   = ( 55,  62,  90, 255)   # grip metálico escuro
PEN_BODY_A = ( 30,  60, 160, 255)   # corpo — metade inferior (mais escuro)
PEN_BODY_B = ( 55, 100, 220, 255)   # corpo — metade superior (mais claro)
PEN_BODY_H = (180, 210, 255, 110)   # faixa de reflexo no corpo
PEN_CAP    = ( 16,  28,  80, 255)   # capuchão azul-marinho
PEN_CAP_H  = ( 80, 110, 200,  90)   # reflexo no capuchão
PEN_RING   = (215, 185,  55, 255)   # anel dourado
PEN_SHADOW = (  0,   0,   0,  80)   # sombra da caneta


def _rr(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width=1):
    """Rounded rectangle — PIL ≥9.2 usa rounded_rectangle; fallback manual."""
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        x0, y0, x1, y1 = xy
        r = radius
        draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
        draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
        for ex, ey in [(x0, y0), (x1 - 2*r, y0), (x0, y1 - 2*r), (x1 - 2*r, y1 - 2*r)]:
            draw.ellipse([ex, ey, ex + 2*r, ey + 2*r], fill=fill)


def _sp(pts, s: float):
    """Escala lista de (x, y) floats para coordenadas inteiras."""
    return [(int(x * s + 0.5), int(y * s + 0.5)) for x, y in pts]


def _lerp_color(c0, c1, t: float):
    """Interpola linearmente duas cores RGBA."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))


# ── Fundo com gradiente radial simulado ─────────────────────────────────────
def _draw_background(img: Image.Image, size: int):
    """Preenche o ícone com gradiente radial do centro (claro) para as bordas (escuro)."""
    cx, cy = size / 2, size / 2
    max_r = math.hypot(cx, cy)
    px = img.load()
    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - cx, y - cy)
            t = min(dist / max_r, 1.0)
            c = _lerp_color(BG_INNER, BG_OUTER, t ** 0.7)
            px[x, y] = c


def draw_frame(size: int) -> Image.Image:
    """Renderiza um frame do ícone no tamanho especificado."""
    s = size / 256.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # ── Fundo ───────────────────────────────────────────────────────────────
    # Primeiro cria uma imagem quadrada com gradiente para depois aplicar mask arredondada
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_background(bg, size)

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    pad = max(1, int(3 * s))
    rad = int(44 * s)
    try:
        md.rounded_rectangle([pad, pad, size - pad, size - pad], radius=rad, fill=255)
    except AttributeError:
        md.ellipse([pad, pad, size - pad, size - pad], fill=255)

    img.paste(bg, mask=mask)
    d = ImageDraw.Draw(img)

    # Borda externa
    _rr(d, [pad, pad, size - pad, size - pad],
        radius=rad, outline=BORDER_C, width=max(1, int(2 * s)))

    # Brilho no canto superior-esquerdo
    if size >= 48:
        shine_pts = _sp([(14, 14), (80, 14), (14, 80)], s)
        shine_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shine_layer)
        sd.polygon(shine_pts, fill=BG_SHINE)
        shine_layer = shine_layer.filter(ImageFilter.GaussianBlur(radius=max(1, int(6 * s))))
        img = Image.alpha_composite(img, shine_layer)
        d = ImageDraw.Draw(img)

    # ── Sombra do papel ──────────────────────────────────────────────────────
    if size >= 32:
        off = max(2, int(4 * s))
        shd_pts = [
            (48 + off,  30 + off),
            (180 + off, 30 + off),
            (180 + off, 220 + off),
            (48 + off,  220 + off),
        ]
        d.polygon(_sp(shd_pts, s), fill=PAPER_SHD)

    # ── Folha de papel ───────────────────────────────────────────────────────
    px0, py0 = 48.0,  32.0
    px1, py1 = 178.0, 218.0
    fold = 34.0

    paper_body = [
        (px0,        py0),
        (px1 - fold, py0),
        (px1,        py0 + fold),
        (px1,        py1),
        (px0,        py1),
    ]
    d.polygon(_sp(paper_body, s), fill=PAPER_W)

    # Dobra com dois triângulos (face + sombra)
    fold_face = [(px1 - fold, py0), (px1, py0 + fold), (px1 - fold, py0 + fold)]
    d.polygon(_sp(fold_face, s), fill=PAPER_FOLD)
    # Aresta da dobra
    d.line(_sp([(px1 - fold, py0), (px1, py0 + fold)], s),
           fill=PAPER_EDGE, width=max(1, int(2 * s)))

    # ── Monograma "Z7" ───────────────────────────────────────────────────────
    if size >= 48:
        # Renderizado geometricamente para máxima nitidez em qualquer tamanho
        # Letra "Z" (canto superior esquerdo do papel)
        zx, zy = 62.0, 52.0
        zw, zh = 36.0, 34.0
        lw_m = max(2, int(4 * s))
        # barra superior
        d.line(_sp([(zx, zy), (zx + zw, zy)], s), fill=MONO_COLOR, width=lw_m)
        # diagonal
        d.line(_sp([(zx + zw, zy), (zx, zy + zh)], s), fill=MONO_COLOR, width=lw_m)
        # barra inferior
        d.line(_sp([(zx, zy + zh), (zx + zw, zy + zh)], s), fill=MONO_COLOR, width=lw_m)

        # Número "7"
        sx, sy = zx + zw + 8.0, zy
        sw, sh = 26.0, 34.0
        # barra superior do 7
        d.line(_sp([(sx, sy), (sx + sw, sy)], s), fill=MONO_COLOR, width=lw_m)
        # perna do 7
        d.line(_sp([(sx + sw, sy), (sx + 6, sy + sh)], s), fill=MONO_COLOR, width=lw_m)
        # traço médio do 7
        d.line(_sp([(sx + 5, sy + sh * 0.5), (sx + sw - 4, sy + sh * 0.5)], s),
               fill=MONO_COLOR, width=max(1, int(2.5 * s)))

    # Linhas de texto abaixo do monograma
    if size >= 32:
        lx0, lx1 = px0 + 12, px1 - 8
        lw_t = max(1, int(3 * s))
        y_base = 108.0 if size >= 48 else 90.0
        lines = [0.0, 22.0, 44.0, 66.0]
        for i, dy in enumerate(lines):
            rx = lx1 if i < 3 else lx0 + (lx1 - lx0) * 0.5
            d.line(_sp([(lx0, y_base + dy), (rx, y_base + dy)], s),
                   fill=LINE_C, width=lw_t)

    # ── Caneta tinteiro ──────────────────────────────────────────────────────
    NIB_TIP = (66.0,  200.0)
    CAP_END = (196.0,  46.0)

    dx = CAP_END[0] - NIB_TIP[0]
    dy = CAP_END[1] - NIB_TIP[1]
    L  = math.hypot(dx, dy)

    ux, uy = dx / L, dy / L       # eixo caneta (bico → cap)
    px_, py_ = -uy, ux            # perpendicular (lado direito)

    def P(t: float, w: float = 0.0):
        return (NIB_TIP[0] + t * ux + w * px_,
                NIB_TIP[1] + t * uy + w * py_)

    def quad(t0, t1, w0, w1):
        return [P(t0, +w0), P(t1, +w1), P(t1, -w1), P(t0, -w0)]

    T_NIB_END  =  28.0
    T_GRIP_END =  56.0
    T_R1_S     =  58.0
    T_R1_E     =  66.0
    T_MID      = (T_R1_E + (L - 20)) / 2   # ponto médio do corpo (split de cor)
    T_BODY_END = L - 20.0
    T_R2_S     = T_BODY_END + 2.0
    T_R2_E     = T_BODY_END + 10.0
    T_CAP_END  = L

    W_NIB  =  7.0
    W_GRIP =  9.0
    W_BODY = 11.5
    W_CAP  = 12.5
    W_RING = 13.5

    # Sombra da caneta
    if size >= 32:
        off = max(2, int(3 * s))
        for poly in [
            quad(0,          T_NIB_END,  0,      W_NIB),
            quad(T_NIB_END,  T_GRIP_END, W_GRIP, W_GRIP),
            quad(T_R1_E,     T_BODY_END, W_BODY, W_BODY),
            quad(T_R2_E,     T_CAP_END,  W_CAP,  W_CAP),
        ]:
            d.polygon([(int(x * s + off + 0.5), int(y * s + off + 0.5))
                       for x, y in poly], fill=PEN_SHADOW)

    # Bico: face escura + face clara
    nb_r = P(T_NIB_END, +W_NIB)
    nb_l = P(T_NIB_END, -W_NIB)
    nb_c = P(T_NIB_END,  0.0)
    d.polygon(_sp([NIB_TIP, nb_r, nb_l], s), fill=PEN_NIB_D)
    d.polygon(_sp([NIB_TIP, nb_r, nb_c], s), fill=PEN_NIB_L)

    # Ponto de tinta
    if size >= 48:
        tx, ty = int(NIB_TIP[0] * s + 0.5), int(NIB_TIP[1] * s + 0.5)
        rd = max(2, int(3.5 * s))
        d.ellipse([tx - rd, ty - rd, tx + rd, ty + rd], fill=PEN_INK)

    # Grip
    d.polygon(_sp(quad(T_NIB_END, T_GRIP_END, W_GRIP, W_GRIP), s), fill=PEN_GRIP)

    # Anel 1
    if size >= 32:
        d.polygon(_sp(quad(T_R1_S, T_R1_E, W_RING, W_RING), s), fill=PEN_RING)

    # Corpo bicolor (metade traseira mais escura, dianteira mais clara)
    if size >= 64:
        d.polygon(_sp(quad(T_R1_E, T_MID,      W_BODY, W_BODY), s), fill=PEN_BODY_A)
        d.polygon(_sp(quad(T_MID,  T_BODY_END,  W_BODY, W_BODY), s), fill=PEN_BODY_B)
    else:
        d.polygon(_sp(quad(T_R1_E, T_BODY_END, W_BODY, W_BODY), s), fill=PEN_BODY_A)

    # Reflexo de vidro no corpo (faixa diagonal)
    if size >= 48:
        hl_s = P(T_R1_E + 10, -(W_BODY - 4))
        hl_e = P(T_BODY_END - 10, -(W_BODY - 4))
        d.line(_sp([hl_s, hl_e], s), fill=PEN_BODY_H, width=max(1, int(2 * s)))

    # Anel 2
    if size >= 32:
        d.polygon(_sp(quad(T_R2_S, T_R2_E, W_RING, W_RING), s), fill=PEN_RING)

    # Capuchão
    d.polygon(_sp(quad(T_R2_E, T_CAP_END, W_CAP, W_CAP), s), fill=PEN_CAP)
    cap_c = P(T_CAP_END, 0.0)
    rc = int(W_CAP * s + 0.5)
    ccx, ccy = int(cap_c[0] * s + 0.5), int(cap_c[1] * s + 0.5)
    d.ellipse([ccx - rc, ccy - rc, ccx + rc, ccy + rc], fill=PEN_CAP)

    # Reflexo no capuchão
    if size >= 48:
        hl_cs = P(T_R2_E + 6, -(W_CAP - 4))
        hl_ce = P(T_CAP_END - 6, -(W_CAP - 4))
        d.line(_sp([hl_cs, hl_ce], s), fill=PEN_CAP_H, width=max(1, int(2 * s)))

    # Clip dourado no capuchão
    if size >= 48:
        cl_s = P(T_R2_E + 6, -(W_CAP + 1.5))
        cl_e = P(T_CAP_END - 6, -(W_CAP + 1.5))
        d.line(_sp([cl_s, cl_e], s), fill=PEN_RING, width=max(1, int(3 * s)))

    return img


def build_ico(out_path: Path):
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [draw_frame(sz) for sz in sizes]

    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f"✓  {out_path}  ({out_path.stat().st_size // 1024} KB, {len(sizes)} sizes)")


if __name__ == "__main__":
    out = Path(__file__).parent / "icon.ico"
    build_ico(out)



# ── Cores da paleta do app (ui.py) ─────────────────────────────────────────
CARD    = (26,  29,  46, 255)   # #1a1d2e  fundo do ícone
BORDER  = (46,  49,  80, 200)   # #2e3150  borda suave
PAPER   = (210, 218, 240, 255)  # papel levemente azulado
PAPER_F = (158, 172, 210, 255)  # dobra do papel (mais escura)
LINE    = (120, 138, 185, 140)  # linhas de texto (semitransparente)
SHADOW  = (  0,   0,   0,  90)  # sombra da caneta

# Caneta tinteiro
PEN_NIB    = (232, 196,  72, 255)  # bico dourado
PEN_NIB_D  = (155, 118,  28, 210)  # face escura do bico
PEN_GRIP   = ( 52,  58,  82, 255)  # grip cinza-metálico
PEN_BODY   = ( 22,  44, 118, 255)  # corpo azul (accent do app)
PEN_BODY_H = ( 80, 120, 200, 130)  # reflexo lateral no corpo
PEN_CAP    = ( 16,  30,  82, 255)  # capuchão azul-marinho
PEN_RING   = (200, 172,  58, 255)  # anel dourado
PEN_CLIP   = (200, 172,  58, 255)  # clip dourado


def _rr(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, width=1):
    """Rounded rectangle helper (PIL <9.2 compat)."""
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        x0, y0, x1, y1 = xy
        r = radius
        draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
        draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
        for ex, ey in [(x0, y0), (x1-2*r, y0), (x0, y1-2*r), (x1-2*r, y1-2*r)]:
            draw.ellipse([ex, ey, ex + 2*r, ey + 2*r], fill=fill)


def _sp(pts, s: float):
    """Scale float (x, y) tuples to int pixel coordinates."""
    return [(int(x * s + 0.5), int(y * s + 0.5)) for x, y in pts]


def draw_frame(size: int) -> Image.Image:
    """Render one icon frame at the given pixel size."""
    s = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── Background rounded square ──────────────────────────────────────────
    pad = max(1, int(4 * s))
    _rr(d, [pad, pad, size - pad, size - pad],
        radius=int(44 * s), fill=CARD, outline=BORDER, width=max(1, int(2 * s)))

    # ── Folha de papel com canto dobrado ──────────────────────────────────
    x1, y1 = 48.0, 30.0
    x2, y2 = 180.0, 220.0
    fold = 36.0

    paper_body = [
        (x1,        y1),
        (x2 - fold, y1),
        (x2,        y1 + fold),
        (x2,        y2),
        (x1,        y2),
    ]
    d.polygon(_sp(paper_body, s), fill=PAPER)

    fold_tri = [
        (x2 - fold, y1),
        (x2,        y1 + fold),
        (x2 - fold, y1 + fold),
    ]
    d.polygon(_sp(fold_tri, s), fill=PAPER_F)

    # Linhas de texto no papel
    lx1 = x1 + 13
    lx2 = x2 - 8
    lx2s = x2 - fold - 3
    lw = max(1, int(3 * s))
    if size >= 32:
        for ly, lxA, lxB in [
            ( 76, lx1, lx2s),
            (100, lx1, lx2),
            (124, lx1, lx2),
            (148, lx1, lx2),
            (172, lx1, lx1 + (lx2 - lx1) * 0.55),
        ]:
            if lxB > lxA:
                d.line(_sp([(lxA, ly), (lxB, ly)], s), fill=LINE, width=lw)

    # ── Caneta tinteiro em diagonal ────────────────────────────────────────
    # Eixo: ponta do bico (inferior-esquerda) → topo do capuchão (superior-direita)
    # Coordenadas na grade 256×256.
    NIB_TIP = (62.0, 202.0)
    CAP_END = (193.0,  48.0)

    dx = CAP_END[0] - NIB_TIP[0]   # 131.0
    dy = CAP_END[1] - NIB_TIP[1]   # -154.0
    L  = math.hypot(dx, dy)         # ≈ 201.9

    # Vetor unitário do eixo (bico→cap) e perpendicular
    ux, uy = dx / L, dy / L         # ≈ ( 0.649, -0.763)
    px, py = -uy, ux                # ≈ ( 0.763,  0.649) — lado direito da caneta

    def P(t: float, w: float = 0.0):
        """Ponto a distância t do bico, deslocado w na perpendicular."""
        return (NIB_TIP[0] + t * ux + w * px,
                NIB_TIP[1] + t * uy + w * py)

    def quad(t0: float, t1: float, w0: float, w1: float):
        """Quadrilátero entre duas posições axiais com meias-larguras w0 e w1."""
        return [P(t0, +w0), P(t1, +w1), P(t1, -w1), P(t0, -w0)]

    # Posições axiais (px na grade 256)
    T_NIB_END  =  26.0   # base do bico
    T_GRIP_END =  56.0   # fim da seção de preensão
    T_R1_S     =  59.0   # início do anel 1 (grip/corpo)
    T_R1_E     =  65.0   # fim do anel 1
    T_BODY_END = 152.0   # fim do corpo
    T_R2_S     = 155.0   # início do anel 2 (corpo/capuchão)
    T_R2_E     = 163.0   # fim do anel 2
    T_CAP_END  =   L     # topo do capuchão (≈ 202)

    # Meias-larguras (px na grade 256)
    W_NIB  =  7.0
    W_GRIP =  8.0
    W_BODY = 11.0
    W_CAP  = 12.0
    W_RING = 13.0

    # Sombra suave da caneta (offset uniforme)
    if size >= 32:
        off = max(2, int(3 * s))
        for poly in [
            quad(0,         T_NIB_END,  0,      W_NIB),
            quad(T_NIB_END, T_GRIP_END, W_NIB,  W_GRIP),
            quad(T_R1_E,    T_BODY_END, W_BODY, W_BODY),
            quad(T_R2_E,    T_CAP_END,  W_CAP,  W_CAP),
        ]:
            d.polygon([(int(x * s + off + 0.5), int(y * s + off + 0.5))
                       for x, y in poly], fill=SHADOW)

    # Bico (triângulo dourado com face clara e escura)
    nb_r = P(T_NIB_END, +W_NIB)
    nb_l = P(T_NIB_END, -W_NIB)
    nb_c = P(T_NIB_END,  0.0)
    d.polygon(_sp([NIB_TIP, nb_r, nb_l], s), fill=PEN_NIB_D)   # face escura
    d.polygon(_sp([NIB_TIP, nb_r, nb_c], s), fill=PEN_NIB)     # face clara

    # Ponto de tinta na ponta do bico
    if size >= 48:
        tx, ty = int(NIB_TIP[0] * s + 0.5), int(NIB_TIP[1] * s + 0.5)
        rd = max(2, int(3 * s))
        d.ellipse([tx - rd, ty - rd, tx + rd, ty + rd], fill=PEN_NIB)

    # Seção de preensão (grip)
    d.polygon(_sp(quad(T_NIB_END, T_GRIP_END, W_GRIP, W_GRIP), s), fill=PEN_GRIP)

    # Anel 1 (grip / corpo)
    if size >= 32:
        d.polygon(_sp(quad(T_R1_S, T_R1_E, W_RING, W_RING), s), fill=PEN_RING)

    # Corpo (barrel)
    d.polygon(_sp(quad(T_R1_E, T_BODY_END, W_BODY, W_BODY), s), fill=PEN_BODY)

    # Reflexo lateral no corpo
    if size >= 48:
        hl_s = P(T_R1_E + 8, -(W_BODY - 3))
        hl_e = P(T_BODY_END - 8, -(W_BODY - 3))
        d.line(_sp([hl_s, hl_e], s), fill=PEN_BODY_H, width=max(1, int(2 * s)))

    # Anel 2 (corpo / capuchão)
    if size >= 32:
        d.polygon(_sp(quad(T_R2_S, T_R2_E, W_RING, W_RING), s), fill=PEN_RING)

    # Capuchão
    d.polygon(_sp(quad(T_R2_E, T_CAP_END, W_CAP, W_CAP), s), fill=PEN_CAP)

    # Topo arredondado do capuchão (círculo)
    cap_center = P(T_CAP_END, 0.0)
    r_cap = int(W_CAP * s + 0.5)
    cx, cy = int(cap_center[0] * s + 0.5), int(cap_center[1] * s + 0.5)
    d.ellipse([cx - r_cap, cy - r_cap, cx + r_cap, cy + r_cap], fill=PEN_CAP)

    # Clip dourado (faixa lateral no capuchão, lado superior)
    if size >= 48:
        cl_s = P(T_R2_E + 5, -(W_CAP + 1))
        cl_e = P(T_CAP_END - 5, -(W_CAP + 1))
        d.line(_sp([cl_s, cl_e], s), fill=PEN_CLIP, width=max(1, int(2.5 * s)))

    return img


def build_ico(out_path: Path):
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [draw_frame(sz) for sz in sizes]

    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f"✓  {out_path}  ({out_path.stat().st_size // 1024} KB, {len(sizes)} sizes)")


if __name__ == "__main__":
    out = Path(__file__).parent / "icon.ico"
    build_ico(out)
