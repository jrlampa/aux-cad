# -*- coding: utf-8 -*-
"""
Script oficial de geração da Identidade Visual e Assets do OXCAD.
Gera de forma determinística e 100% reprodutível:
- oxcad.svg (Fonte vetorial mestre 512x512)
- oxcad.png (Master raster 1024x1024 com transparência)
- oxcad.ico (Ícone Windows multi-resolução: 16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256)
- oxcad_{16,24,32,48,64,128,256}.png (Assets raster individuais)
- oxcad_mono.png (Versão monocromática para validação de contraste)
- oxcad_wordmark.svg / oxcad_wordmark.png (Versão com símbolo + tipografia)
"""

from pathlib import Path
import math
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Paleta de Cores Oficial OXCAD
COLOR_CYAN_PRIMARY = "#4EA8DE"     # Azul Elétrico CAD (Destaque principal)
COLOR_CYAN_LIGHT   = "#72EFDD"     # Ciano Técnico / Snap highlights
COLOR_BLUE_DEEP    = "#0077B6"     # Azul Profundo Engenharia
COLOR_GRAPHITE     = "#1E222D"     # Grafite Escuro Técnico
COLOR_SLATE_BORDER = "#2B3245"     # Contorno / Acento técnico
COLOR_WHITE        = "#FFFFFF"     # Nós de precisão


def gerar_svg_mestre() -> str:
    """Gera o SVG mestre do símbolo monograma geométrico OX (512x512)."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <!-- Gradiente do Anel O (Azul Tecnico CAD) -->
    <linearGradient id="oxRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{COLOR_CYAN_LIGHT}" />
      <stop offset="50%" stop-color="{COLOR_CYAN_PRIMARY}" />
      <stop offset="100%" stop-color="{COLOR_BLUE_DEEP}" />
    </linearGradient>

    <!-- Gradiente do Eixo X (Grafite Tecnico / Precision) -->
    <linearGradient id="oxXGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2D3748" />
      <stop offset="50%" stop-color="{COLOR_GRAPHITE}" />
      <stop offset="100%" stop-color="#141824" />
    </linearGradient>

    <!-- Filtro de sombra sutil de precisao -->
    <filter id="oxDropShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.35" />
    </filter>

    <!-- Mascara de corte para o anel O (gap nos cruzamentos do X) -->
    <mask id="ringGapMask">
      <rect x="0" y="0" width="512" height="512" fill="white" />
      <!-- Cortes diagonais de folga tecnica (kerf) onde a viga NW-SE sobrepoe -->
      <line x1="90" y1="90" x2="422" y2="422" stroke="black" stroke-width="84" stroke-linecap="square" />
    </mask>
  </defs>

  <!-- GRUPO PRINCIPAL COM FILTRO DE ELEVACAO -->
  <g filter="url(#oxDropShadow)">
    <!-- 1. VIGA DIAGONAL DO X (SW -> NE): Camada de Fundo -->
    <line x1="106" y1="406" x2="406" y2="106" 
          stroke="url(#oxXGrad)" stroke-width="64" stroke-linecap="round" />
    <line x1="106" y1="406" x2="406" y2="106" 
          stroke="{COLOR_SLATE_BORDER}" stroke-width="64" stroke-linecap="round" fill="none" opacity="0.3" />

    <!-- 2. ANEL 'O' (Circulo Tecnico com Mascara de Gap nos cruzamentos) -->
    <circle cx="256" cy="256" r="160" 
            fill="none" stroke="url(#oxRingGrad)" stroke-width="60" 
            mask="url(#ringGapMask)" />

    <!-- 3. VIGA DIAGONAL DO X (NW -> SE): Camada Sobreposta (Passa por cima do O com folga tecnica) -->
    <line x1="106" y1="106" x2="406" y2="406" 
          stroke="url(#oxXGrad)" stroke-width="64" stroke-linecap="round" />

    <!-- Filete de contorno tecnico de precisao na viga sobreposta -->
    <line x1="106" y1="106" x2="406" y2="406" 
          stroke="{COLOR_CYAN_PRIMARY}" stroke-width="2" stroke-linecap="round" opacity="0.6" />

    <!-- 4. NUCLEO DE INTERSECCAO CENTRAL (Retículo / Mira CAD) -->
    <rect x="238" y="238" width="36" height="36" rx="4"
          fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="3"
          transform="rotate(45 256 256)" />
    <circle cx="256" cy="256" r="4" fill="{COLOR_WHITE}" />

    <!-- 5. NOS DE PRECISAO CAD (Snap Points nos 4 terminais do X) -->
    <circle cx="106" cy="106" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="3.5" />
    <circle cx="106" cy="106" r="4.5" fill="{COLOR_WHITE}" />

    <circle cx="406" cy="406" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="3.5" />
    <circle cx="406" cy="406" r="4.5" fill="{COLOR_WHITE}" />

    <circle cx="406" cy="106" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="3.5" />
    <circle cx="406" cy="106" r="4.5" fill="{COLOR_WHITE}" />

    <circle cx="106" cy="406" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="3.5" />
    <circle cx="106" cy="406" r="4.5" fill="{COLOR_WHITE}" />

    <!-- 6. MARCADORES DE EIXOS CARTESIANOS CAD -->
    <line x1="256" y1="28" x2="256" y2="48" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" stroke-linecap="round" />
    <line x1="256" y1="464" x2="256" y2="484" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" stroke-linecap="round" />
    <line x1="28" y1="256" x2="48" y2="256" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" stroke-linecap="round" />
    <line x1="464" y1="256" x2="484" y2="256" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" stroke-linecap="round" />
  </g>
</svg>
"""
    return svg


def gerar_svg_wordmark() -> str:
    """Gera o SVG do logotipo horizontal OXCAD (simbolo + tipografia tecnica)."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 320" width="1024" height="320">
  <defs>
    <linearGradient id="wmRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{COLOR_CYAN_LIGHT}" />
      <stop offset="100%" stop-color="{COLOR_CYAN_PRIMARY}" />
    </linearGradient>
  </defs>

  <!-- SIMBOLO REDUZIDO (Escala 0.5, Centro em x=140, y=160) -->
  <g transform="translate(140, 160) scale(0.48) translate(-256, -256)">
    <!-- Viga SW-NE -->
    <line x1="106" y1="406" x2="406" y2="106" stroke="{COLOR_GRAPHITE}" stroke-width="64" stroke-linecap="round" />
    <!-- Anel O -->
    <circle cx="256" cy="256" r="160" fill="none" stroke="url(#wmRingGrad)" stroke-width="60" />
    <!-- Viga NW-SE -->
    <line x1="106" y1="106" x2="406" y2="406" stroke="{COLOR_GRAPHITE}" stroke-width="64" stroke-linecap="round" />
    <!-- Nucleo -->
    <rect x="238" y="238" width="36" height="36" rx="4" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="3" transform="rotate(45 256 256)" />
    <circle cx="256" cy="256" r="5" fill="{COLOR_WHITE}" />
    <!-- Snap points -->
    <circle cx="106" cy="106" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" />
    <circle cx="406" cy="406" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" />
    <circle cx="406" cy="106" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" />
    <circle cx="106" cy="406" r="14" fill="{COLOR_GRAPHITE}" stroke="{COLOR_CYAN_LIGHT}" stroke-width="4" />
  </g>

  <!-- WORDMARK: OXCAD -->
  <text x="310" y="180" font-family="'Segoe UI', 'Outfit', 'Inter', 'Helvetica', sans-serif" font-size="110" font-weight="800" fill="#FFFFFF" letter-spacing="4">
    OX<tspan fill="{COLOR_CYAN_PRIMARY}">CAD</tspan>
  </text>

  <!-- SUBTITULO TECNICO -->
  <text x="316" y="228" font-family="'Segoe UI', 'Inter', 'Helvetica', sans-serif" font-size="20" font-weight="500" fill="#9E9EB0" letter-spacing="3">
    AMBIENTE INTEGRADO DE AUTOMAÇÃO CAD
  </text>

  <!-- LINHA DE BASE DE ENGENHARIA -->
  <line x1="316" y1="248" x2="880" y2="248" stroke="{COLOR_SLATE_BORDER}" stroke-width="2" />
  <circle cx="316" cy="248" r="3" fill="{COLOR_CYAN_PRIMARY}" />
  <circle cx="880" cy="248" r="3" fill="{COLOR_CYAN_PRIMARY}" />
</svg>
"""
    return svg


def renderizar_raster_geometria(tamanho: int, modo_mono: bool = False) -> Image.Image:
    """
    Renderiza diretamente a geometria vetorial precisa do OXCAD em alta resolução
    com supersampling 4x para anti-aliasing cirúrgico mesmo em 16x16 ou 1024x1024.
    """
    fator_ss = 4
    dim_ss = tamanho * fator_ss
    img = Image.new("RGBA", (dim_ss, dim_ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Cores de acordo com modo
    if modo_mono:
        c_ring = (255, 255, 255, 255)
        c_ring_glow = (255, 255, 255, 255)
        c_x1 = (180, 180, 180, 255)
        c_x2 = (140, 140, 140, 255)
        c_core = (255, 255, 255, 255)
        c_dot = (0, 0, 0, 255)
        c_tick = (255, 255, 255, 255)
    else:
        c_ring = (78, 168, 222, 255)        # #4EA8DE
        c_ring_glow = (114, 239, 221, 255)  # #72EFDD
        c_x1 = (30, 34, 45, 255)            # #1E222D
        c_x2 = (24, 28, 38, 255)            # #181C26
        c_core = (114, 239, 221, 255)
        c_dot = (255, 255, 255, 255)
        c_tick = (114, 239, 221, 220)

    # Escala para dim_ss baseada em grid 512
    s = dim_ss / 512.0
    cx, cy = 256.0 * s, 256.0 * s

    # 1. Eixo SW-NE do X
    x_w = 62.0 * s
    draw.line([(106.0 * s, 406.0 * s), (406.0 * s, 106.0 * s)], fill=c_x1, width=int(round(x_w)))

    # 2. Anel O
    r_med = 160.0 * s
    ring_w = 58.0 * s
    bbox_ring = [cx - r_med, cy - r_med, cx + r_med, cy + r_med]

    if tamanho >= 32:
        gap_ang = 14.0  # graus de folga técnica
        draw.arc(bbox_ring, start=45 + gap_ang, end=225 - gap_ang, fill=c_ring, width=int(round(ring_w)))
        draw.arc(bbox_ring, start=225 + gap_ang, end=360 + 45 - gap_ang, fill=c_ring, width=int(round(ring_w)))
    else:
        draw.ellipse(bbox_ring, outline=c_ring, width=int(round(ring_w)))

    # 3. Eixo NW-SE do X (passa por cima)
    draw.line([(106.0 * s, 106.0 * s), (406.0 * s, 406.0 * s)], fill=c_x2, width=int(round(x_w)))

    if tamanho >= 32 and not modo_mono:
        draw.line([(106.0 * s, 106.0 * s), (406.0 * s, 406.0 * s)], fill=c_ring_glow, width=max(1, int(round(2.0 * s))))

    # 4. Snap points / Terminais (4 cantos do X)
    pts = [
        (106.0 * s, 106.0 * s),
        (406.0 * s, 406.0 * s),
        (406.0 * s, 106.0 * s),
        (106.0 * s, 406.0 * s),
    ]
    r_snap_out = 14.0 * s
    r_snap_in = 4.5 * s
    for px, py in pts:
        if tamanho >= 32:
            draw.ellipse([px - r_snap_out, py - r_snap_out, px + r_snap_out, py + r_snap_out], fill=c_x1, outline=c_ring_glow, width=max(1, int(round(3.0 * s))))
            draw.ellipse([px - r_snap_in, py - r_snap_in, px + r_snap_in, py + r_snap_in], fill=c_dot)
        else:
            draw.ellipse([px - r_snap_out * 0.8, py - r_snap_out * 0.8, px + r_snap_out * 0.8, py + r_snap_out * 0.8], fill=c_ring_glow)

    # 5. Núcleo central
    r_core = 16.0 * s
    if tamanho >= 32:
        draw.rectangle([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=c_x1, outline=c_core, width=max(1, int(round(2.5 * s))))
        draw.ellipse([cx - 4.0 * s, cy - 4.0 * s, cx + 4.0 * s, cy + 4.0 * s], fill=c_dot)
    else:
        draw.rectangle([cx - r_core * 0.8, cy - r_core * 0.8, cx + r_core * 0.8, cy + r_core * 0.8], fill=c_core)

    # 6. Eixos cartesianos ticks se tamanho >= 64
    if tamanho >= 64:
        tick_w = max(1, int(round(3.5 * s)))
        draw.line([(cx, 30.0 * s), (cx, 48.0 * s)], fill=c_tick, width=tick_w)
        draw.line([(cx, 464.0 * s), (cx, 482.0 * s)], fill=c_tick, width=tick_w)
        draw.line([(30.0 * s, cy), (48.0 * s, cy)], fill=c_tick, width=tick_w)
        draw.line([(464.0 * s, cy), (482.0 * s, cy)], fill=c_tick, width=tick_w)

    img_final = img.resize((tamanho, tamanho), Image.Resampling.LANCZOS)
    return img_final


def renderizar_wordmark_raster(largura: int = 1024, altura: int = 320) -> Image.Image:
    """Renderiza a versão wordmark rasterizada com tipografia elegante e nítida."""
    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Renderiza símbolo reduzido no lado esquerdo
    simbolo = renderizar_raster_geometria(220)
    img.paste(simbolo, (30, 50), simbolo)

    # Tipografia: Tenta carregar fonte do sistema ou desenha vetorialmente
    fonte_carregada = False
    for font_name in ["segoeui.ttf", "arial.ttf", "tahoma.ttf"]:
        try:
            fonte_oxcad = ImageFont.truetype(font_name, 84)
            fonte_sub = ImageFont.truetype(font_name, 18)
            fonte_carregada = True
            break
        except Exception:
            continue

    if fonte_carregada:
        draw.text((275, 75), "OX", fill=(255, 255, 255, 255), font=fonte_oxcad)
        # Calcula largura de "OX" para concatenar "CAD" colorido
        bbox_ox = draw.textbbox((275, 75), "OX", font=fonte_oxcad)
        draw.text((bbox_ox[2] + 4, 75), "CAD", fill=(78, 168, 222, 255), font=fonte_oxcad)

        draw.text((280, 180), "AMBIENTE INTEGRADO DE AUTOMAÇÃO CAD", fill=(158, 158, 176, 255), font=fonte_sub)
    else:
        draw.text((275, 75), "OXCAD", fill=(78, 168, 222, 255))
        draw.text((280, 180), "AMBIENTE INTEGRADO DE AUTOMAÇÃO CAD", fill=(158, 158, 176, 255))

    # Linha guia técnica
    draw.line([(280, 215), (960, 215)], fill=(43, 50, 69, 255), width=2)
    draw.ellipse([(278, 213), (282, 217)], fill=(78, 168, 222, 255))
    draw.ellipse([(958, 213), (962, 217)], fill=(78, 168, 222, 255))

    return img


def gerar_todos_os_assets():
    """Gera o catálogo completo oficial de assets OXCAD."""
    print("Iniciando geração de assets visuais OXCAD...")

    # 1. SVGs Mestres
    svg_mestre = gerar_svg_mestre()
    (ASSETS_DIR / "oxcad.svg").write_text(svg_mestre, encoding="utf-8")
    print(f"[OK] Gravado: {ASSETS_DIR / 'oxcad.svg'}")

    svg_wordmark = gerar_svg_wordmark()
    (ASSETS_DIR / "oxcad_wordmark.svg").write_text(svg_wordmark, encoding="utf-8")
    print(f"[OK] Gravado: {ASSETS_DIR / 'oxcad_wordmark.svg'}")

    # 2. Imagem Mestre 1024x1024
    img_1024 = renderizar_raster_geometria(1024)
    img_1024.save(ASSETS_DIR / "oxcad.png", format="PNG", optimize=True)
    print(f"[OK] Gravado: {ASSETS_DIR / 'oxcad.png'} (1024x1024, RGBA)")

    # 3. Versão Monocromática (validação de alto contraste e escala de cinza)
    img_mono = renderizar_raster_geometria(1024, modo_mono=True)
    img_mono.save(ASSETS_DIR / "oxcad_mono.png", format="PNG", optimize=True)
    print(f"[OK] Gravado: {ASSETS_DIR / 'oxcad_mono.png'} (1024x1024, Monocromático)")

    # 4. Wordmark Raster
    img_wm = renderizar_wordmark_raster()
    img_wm.save(ASSETS_DIR / "oxcad_wordmark.png", format="PNG", optimize=True)
    print(f"[OK] Gravado: {ASSETS_DIR / 'oxcad_wordmark.png'} (1024x320, RGBA)")

    # 5. Resoluções Específicas
    tamanhos = [16, 24, 32, 48, 64, 128, 256]
    imagens_dict = {}

    for t in tamanhos:
        img_t = renderizar_raster_geometria(t)
        caminho_t = ASSETS_DIR / f"oxcad_{t}.png"
        img_t.save(caminho_t, format="PNG", optimize=True)
        print(f"[OK] Gravado: {caminho_t} ({t}x{t}, RGBA)")
        imagens_dict[t] = img_t

    # 6. Ícone Windows (.ico) multi-frame legítimo
    caminho_ico = ASSETS_DIR / "oxcad.ico"
    # PIL salva ICO com múltiplas resoluções a partir da maior
    img_256 = imagens_dict[256]
    outras_imgs = [imagens_dict[t] for t in [16, 24, 32, 48, 64, 128]]
    img_256.save(
        caminho_ico,
        format="ICO",
        sizes=[(t, t) for t in tamanhos],
        append_images=outras_imgs,
    )
    print(f"[OK] Gravado: {caminho_ico} (Multi-frame ICO: 16, 24, 32, 48, 64, 128, 256)")

    print("\nTodos os assets foram gerados com sucesso!")


if __name__ == "__main__":
    gerar_todos_os_assets()
