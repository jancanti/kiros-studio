"""Motor de Layout Determinístico (Seção 28).

Responsável pelo design gráfico final, tipografia, logo e posicionamento exato.
NÃO utiliza chamadas de LLM para posicionamento, tipografia, cálculo ou renderização.
"""
from html import escape
import json
from typing import Any, Dict, List, Optional, Tuple

from kiros.layout.models import (
    FORMAT_4_5,
    FORMAT_9_16,
    FORMAT_DIMENSIONS,
    SAFE_AREAS,
    ELEMENT_TYPES,
    VALID_FORMATS,
    HeadlineElement,
    ImageElement,
    LogoElement,
    CTAElement,
    DecorativeElement,
    SlideLayout,
    LayoutValidationError,
)


class LayoutEngine:
    """Motor determinístico para cálculo de geometria, proporções e renderização SVG/layout em 4:5 e 9:16."""

    def __init__(self):
        pass

    def get_dimensions(self, fmt: str) -> Tuple[int, int]:
        if fmt not in FORMAT_DIMENSIONS:
            raise LayoutValidationError(f"Formato inválido: '{fmt}'. Suportados: {', '.join(VALID_FORMATS)}")
        return FORMAT_DIMENSIONS[fmt]

    def get_safe_area(self, fmt: str) -> Dict[str, int]:
        if fmt not in SAFE_AREAS:
            raise LayoutValidationError(f"Formato inválido: '{fmt}'. Suportados: {', '.join(VALID_FORMATS)}")
        return SAFE_AREAS[fmt]

    def validate_proportions(self, fmt: str) -> bool:
        """Verifica rigorosamente a proporção matemática do formato (0.8 para 4:5, 0.5625 para 9:16)."""
        w, h = self.get_dimensions(fmt)
        ratio = w / h
        if fmt == FORMAT_4_5:
            # 1080 / 1350 = 0.8
            return abs(ratio - 0.8) < 1e-6
        elif fmt == FORMAT_9_16:
            # 1080 / 1920 = 0.5625
            return abs(ratio - 0.5625) < 1e-6
        return False

    def validate_safe_zones(self, layout: SlideLayout) -> List[str]:
        """Garante ausência de cortes calculando se elementos essenciais estão dentro das safe areas."""
        fmt = layout.format
        w, h = self.get_dimensions(fmt)
        safe = self.get_safe_area(fmt)
        warnings = []

        # Safe boundaries
        min_x = safe['left']
        max_x = w - safe['right']
        min_y = safe['top']
        max_y = h - safe['bottom']

        # 1. Headline
        hl = layout.headline
        if hl.position_x < min_x:
            warnings.append(f"Headline position_x ({hl.position_x}) ultrapassa margem esquerda segura ({min_x}).")
        if hl.position_x + hl.max_width > max_x:
            warnings.append(f"Headline largura máxima ultrapassa margem direita segura ({max_x}).")
        if hl.position_y < min_y:
            warnings.append(f"Headline position_y ({hl.position_y}) invade safe zone superior ({min_y}).")
        if hl.position_y > max_y:
            warnings.append(f"Headline position_y ({hl.position_y}) invade safe zone inferior ({max_y}).")

        # 2. Logo
        lg = layout.logo
        if lg.position_x < min_x or lg.position_x > max_x:
            warnings.append(f"Logo position_x ({lg.position_x}) fora dos limites horizontais ({min_x} a {max_x}).")
        if lg.position_y < min_y or lg.position_y > max_y:
            warnings.append(f"Logo position_y ({lg.position_y}) fora dos limites verticais seguros ({min_y} a {max_y}).")

        # 3. CTA
        cta = layout.cta
        if cta.position_x < min_x or cta.position_x > max_x:
            warnings.append(f"CTA position_x ({cta.position_x}) fora dos limites horizontais ({min_x} a {max_x}).")
        if cta.position_y < min_y or cta.position_y > max_y:
            warnings.append(f"CTA position_y ({cta.position_y}) fora dos limites verticais seguros ({min_y} a {max_y}).")

        return warnings

    def wrap_text(self, text: str, max_chars_per_line: int = 26) -> List[str]:
        """Quebra de linha determinística sem LLM para garantir legibilidade e ausência de cortes."""
        words = (text or '').strip().split()
        if not words:
            return []
        lines = []
        current_line: List[str] = []
        current_len = 0
        for word in words:
            word_len = len(word)
            if current_line and (current_len + 1 + word_len) > max_chars_per_line:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_len = word_len
            else:
                current_line.append(word)
                current_len += (1 if current_line else 0) + word_len
        if current_line:
            lines.append(' '.join(current_line))
        return lines

    def render_svg(self, layout: SlideLayout, show_safe_areas: bool = False) -> str:
        """Renderiza o layout completo em SVG determinístico de alta resolução (1080x1350 ou 1080x1920).

        Não usa LLM: o texto exato, logotipo com proporções mantidas e posicionamento gráfico
        são gerados estritamente com base nos parâmetros do motor.
        """
        fmt = layout.format
        width, height = self.get_dimensions(fmt)
        safe = self.get_safe_area(fmt)

        # 1. Background e Efeito de Iluminação da Imagem
        img = layout.image
        lighting_gradients = {
            'natural_lateral': (
                '<linearGradient id="lightGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
                '<stop offset="0%" stop-color="#fff9f2" stop-opacity="0.22"/>'
                '<stop offset="100%" stop-color="#141815" stop-opacity="0.45"/>'
                '</linearGradient>'
            ),
            'golden_hour': (
                '<linearGradient id="lightGrad" x1="0%" y1="0%" x2="100%" y2="100%">'
                '<stop offset="0%" stop-color="#ffeed6" stop-opacity="0.32"/>'
                '<stop offset="100%" stop-color="#422510" stop-opacity="0.50"/>'
                '</linearGradient>'
            ),
            'soft_studio': (
                '<radialGradient id="lightGrad" cx="50%" cy="45%" r="60%">'
                '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.25"/>'
                '<stop offset="100%" stop-color="#1a1d1b" stop-opacity="0.40"/>'
                '</radialGradient>'
            ),
            'dramatic': (
                '<linearGradient id="lightGrad" x1="0%" y1="30%" x2="100%" y2="100%">'
                '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.10"/>'
                '<stop offset="100%" stop-color="#0b0e0c" stop-opacity="0.75"/>'
                '</linearGradient>'
            ),
            'diffused': (
                '<linearGradient id="lightGrad" x1="50%" y1="0%" x2="50%" y2="100%">'
                '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.15"/>'
                '<stop offset="100%" stop-color="#242926" stop-opacity="0.35"/>'
                '</linearGradient>'
            ),
        }
        chosen_grad = lighting_gradients.get(img.lighting, lighting_gradients['natural_lateral'])

        # Enquadramento gráfico do container da imagem
        framing_scales = {
            'wide': 0.85,
            'medium': 1.0,
            'close-up': 1.25,
            'detail': 1.45,
            'overhead': 1.1,
        }
        f_scale = framing_scales.get(img.framing, 1.0) * img.scale

        # 2. Headline - Quebra determinística e linhas de texto exato
        hl = layout.headline
        max_chars = max(14, int(hl.max_width / (hl.font_size * 0.55)))
        wrapped_lines = self.wrap_text(hl.text, max_chars_per_line=max_chars)
        line_step = int(hl.font_size * hl.line_height)

        headline_tspans = []
        for i, line in enumerate(wrapped_lines):
            dy = '0' if i == 0 else f"{line_step}px"
            headline_tspans.append(
                f'<tspan x="{hl.position_x}" dy="{dy}">{escape(line)}</tspan>'
            )
        headline_tspans_str = ''.join(headline_tspans)

        # 3. Logo da Marca KIROS com Proporção Estritamente Fixa
        lg = layout.logo
        logo_scale = lg.scale
        logo_fill = escape(lg.color)
        logo_x = lg.position_x
        logo_y = lg.position_y
        logo_text = escape(lg.brand_name)

        # 4. CTA (Call To Action)
        cta = layout.cta
        cta_text = escape(cta.text)
        # Cálculo de largura aproximada do botão com base no texto exato
        cta_width = len(cta.text) * int(cta.font_size * 0.6) + (cta.padding_x * 2)
        cta_height = cta.font_size + (cta.padding_y * 2)

        # 5. Elemento Decorativo
        dec = layout.decorative
        dec_svg = ''
        if dec.kind == 'badge':
            dec_svg = (
                f'<g id="decorative" transform="translate({dec.position_x}, {dec.position_y})" opacity="{dec.opacity}">'
                f'<rect width="{dec.width}" height="{dec.height}" rx="4" fill="{escape(dec.fill_color)}" stroke="{escape(dec.stroke_color)}" stroke-width="{dec.stroke_width}"/>'
                f'<text x="{int(dec.width / 2)}" y="{int(dec.height / 2 + 5)}" font-family="Inter, sans-serif" font-size="11" font-weight="600" letter-spacing="1.5" fill="#273b32" text-anchor="middle">{escape(dec.label)}</text>'
                f'</g>'
            )
        elif dec.kind == 'divider':
            dec_svg = (
                f'<g id="decorative" opacity="{dec.opacity}">'
                f'<line x1="{dec.position_x}" y1="{dec.position_y}" x2="{dec.position_x + dec.width}" y2="{dec.position_y}" stroke="{escape(dec.stroke_color)}" stroke-width="{dec.stroke_width}"/>'
                f'</g>'
            )
        elif dec.kind == 'frame':
            dec_svg = (
                f'<g id="decorative" opacity="{dec.opacity}">'
                f'<rect x="{dec.position_x}" y="{dec.position_y}" width="{dec.width}" height="{dec.height}" fill="none" stroke="{escape(dec.stroke_color)}" stroke-width="{dec.stroke_width}"/>'
                f'</g>'
            )

        # Safe area visualization (opcional para debug / revisão visual)
        safe_svg = ''
        if show_safe_areas:
            sw = width - safe['left'] - safe['right']
            sh = height - safe['top'] - safe['bottom']
            safe_svg = (
                f'<g id="safe-area-overlay" opacity="0.6">'
                f'<rect x="{safe["left"]}" y="{safe["top"]}" width="{sw}" height="{sh}" fill="none" stroke="#2563eb" stroke-width="2" stroke-dasharray="8 6"/>'
                f'<text x="{safe["left"] + 10}" y="{safe["top"] + 24}" font-family="Inter, sans-serif" font-size="14" fill="#2563eb" font-weight="600">SAFE AREA ({fmt})</text>'
                f'</g>'
            )

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&amp;family=Rubik:wght@400;500;600;700&amp;display=swap');
      .font-headline {{ font-family: '{escape(hl.font_family)}', 'Rubik', sans-serif; }}
      .font-ui {{ font-family: 'Inter', sans-serif; }}
    </style>
    {chosen_grad}
    <clipPath id="imageClip">
      <rect x="0" y="0" width="{width}" height="{height}"/>
    </clipPath>
  </defs>

  <!-- 1. Camada de Imagem de Fundo e Textura Fotográfica -->
  <g id="image" clip-path="url(#imageClip)">
    <rect width="{width}" height="{height}" fill="#f5efe6"/>
    <!-- Gradiente de ambiente simulando fotografia de alta fidelidade com luz lateral -->
    <rect width="{width}" height="{height}" fill="url(#lightGrad)"/>
    <!-- Ilustração esquemática vetorial do produto em vidro âmbar com pavio / difusor -->
    <g transform="translate({int(width / 2 + img.position_x)}, {int(height * 0.52 + img.position_y)}) scale({f_scale})">
      <!-- Sombra de contato -->
      <ellipse cx="0" cy="220" rx="140" ry="24" fill="#1e1e1e" opacity="0.22"/>
      <!-- Corpo da vela/frasco em vidro âmbar -->
      <rect x="-90" y="-70" width="180" height="280" rx="18" fill="#a45a2a" stroke="#5d3215" stroke-width="4"/>
      <rect x="-82" y="-62" width="164" height="264" rx="12" fill="#8c481d" opacity="0.95"/>
      <!-- Brilho lateral no vidro (fotografia com luz lateral natural) -->
      <path d="M -70 -50 Q -75 60 -70 180" stroke="#ffd9aa" stroke-width="6" stroke-linecap="round" fill="none" opacity="0.45"/>
      <!-- Rótulo de linho natural -->
      <rect x="-65" y="0" width="130" height="130" rx="4" fill="#fcf9f2" stroke="#d5ccb8" stroke-width="2"/>
      <text x="0" y="42" font-family="'Rubik', sans-serif" font-size="14" font-weight="600" fill="#273b32" text-anchor="middle" letter-spacing="2">KIROS</text>
      <line x1="-30" y1="52" x2="30" y2="52" stroke="#273b32" stroke-width="1" opacity="0.4"/>
      <text x="0" y="74" font-family="'Inter', sans-serif" font-size="10" font-weight="500" fill="#4a5550" text-anchor="middle">AROMA NATURAL</text>
      <text x="0" y="92" font-family="'Inter', sans-serif" font-size="9" fill="#7a8580" text-anchor="middle">240g · Sorocaba/SP</text>
      <!-- Tampa em madeira maciça com ranhuras sutis -->
      <rect x="-96" y="-95" width="192" height="30" rx="6" fill="#54361e" stroke="#36200f" stroke-width="2"/>
      <line x1="-80" y1="-80" x2="80" y2="-80" stroke="#785030" stroke-width="1.5" opacity="0.6"/>
      <!-- Chama suave (se iluminação permitir) -->
      <path d="M 0 -105 Q 12 -135 0 -160 Q -12 -135 0 -105 Z" fill="#ffb74d" opacity="0.85"/>
      <ellipse cx="0" cy="-120" rx="4" ry="10" fill="#fff3e0"/>
    </g>
  </g>

  <!-- 2. Camada Decorativa -->
  {dec_svg}

  <!-- 3. Headline Exata e Tipografia Rubik (sem LLM) -->
  <g id="headline" class="font-headline">
    <text x="{hl.position_x}" y="{hl.position_y}" font-size="{hl.font_size}" font-weight="{hl.font_weight}" fill="{escape(hl.color)}" letter-spacing="{hl.letter_spacing}">
      {headline_tspans_str}
    </text>
  </g>

  <!-- 4. Logo Oficial da Marca (Proporções estritamente bloqueadas) -->
  <g id="logo" class="font-ui" transform="translate({logo_x}, {logo_y}) scale({logo_scale})">
    <!-- Emblema botânico estilizado -->
    <g transform="translate(0, -16)">
      <circle cx="16" cy="16" r="16" fill="{logo_fill}"/>
      <path d="M 16 6 C 21 11 21 21 16 26 C 11 21 11 11 16 6 Z" fill="#ffffff"/>
      <circle cx="16" cy="16" r="3" fill="{logo_fill}"/>
    </g>
    <!-- Wordmark da marca -->
    <text x="44" y="8" font-family="'Rubik', sans-serif" font-size="22" font-weight="700" fill="{logo_fill}" letter-spacing="3.5">{logo_text}</text>
    <text x="44" y="24" font-family="'Inter', sans-serif" font-size="9" font-weight="500" fill="{logo_fill}" letter-spacing="2" opacity="0.85">AROMAS · BRASIL</text>
  </g>

  <!-- 5. CTA (Call To Action) com texto exato -->
  <g id="cta" class="font-ui" transform="translate({cta.position_x}, {cta.position_y})">
    <rect width="{cta_width}" height="{cta_height}" rx="{cta.border_radius}" fill="{escape(cta.bg_color)}"/>
    <text x="{int(cta_width / 2)}" y="{int(cta_height / 2 + cta.font_size * 0.35)}" font-size="{cta.font_size}" font-weight="600" fill="{escape(cta.text_color)}" text-anchor="middle" letter-spacing="0.5">
      {cta_text}
    </text>
  </g>

  <!-- Safe area visual indicator para auditoria e teste de ausência de cortes -->
  {safe_svg}
</svg>'''
        return svg

    def adapt_format(self, layout: SlideLayout, target_format: str) -> SlideLayout:
        """Adapta responsivamente um layout entre 4:5 e 9:16 preservando a identidade visual e safe areas."""
        if target_format not in VALID_FORMATS:
            raise LayoutValidationError(f"Formato de destino inválido: '{target_format}'")
        if layout.format == target_format:
            return layout

        current_fmt = layout.format
        target_w, target_h = self.get_dimensions(target_format)
        target_safe = self.get_safe_area(target_format)

        # Clona elementos
        new_layout = SlideLayout(
            id=layout.id,
            campaign_id=layout.campaign_id,
            slide_id=layout.slide_id,
            template_id=layout.template_id,
            format=target_format,
            headline=HeadlineElement.from_dict(layout.headline.to_dict()),
            image=ImageElement.from_dict(layout.image.to_dict()),
            logo=LogoElement.from_dict(layout.logo.to_dict()),
            cta=CTAElement.from_dict(layout.cta.to_dict()),
            decorative=DecorativeElement.from_dict(layout.decorative.to_dict()),
            protection_overrides=dict(layout.protection_overrides),
            is_approved=layout.is_approved,
            approved_at=layout.approved_at,
            approved_by=layout.approved_by,
            created_at=layout.created_at,
            updated_at=layout.updated_at,
        )

        if target_format == FORMAT_9_16:
            # Transição de 4:5 (1350h) para 9:16 (1920h)
            # Safe area do topo no 9:16 é 250px (deve acomodar logo e headline abaixo dela)
            new_layout.logo.position_y = target_safe['top'] + 20
            new_layout.headline.position_y = target_safe['top'] + 120
            new_layout.headline.font_size = max(48, int(layout.headline.font_size * 0.96))
            # Safe area da base no 9:16 é 350px (CTA deve ficar acima dela)
            new_layout.cta.position_y = target_h - target_safe['bottom'] - 60
            new_layout.decorative.position_y = target_h - target_safe['bottom'] - 130
            new_layout.image.position_y = 60
        else:
            # Transição de 9:16 (1920h) para 4:5 (1350h)
            new_layout.logo.position_y = target_safe['top'] + 15
            new_layout.headline.position_y = target_safe['top'] + 85
            new_layout.headline.font_size = min(56, int(layout.headline.font_size * 1.04))
            new_layout.cta.position_y = target_h - target_safe['bottom'] - 50
            new_layout.decorative.position_y = target_h - target_safe['bottom'] - 110
            new_layout.image.position_y = 0

        return new_layout

    def export_svg(self, layout: SlideLayout) -> str:
        """Exporta o SVG final standalone determinístico."""
        return self.render_svg(layout, show_safe_areas=False)

    def export_layout_data(self, layout: SlideLayout) -> Dict[str, Any]:
        """Exporta metadados estruturados e SVG do layout para distribuição determinística."""
        w, h = self.get_dimensions(layout.format)
        return {
            'layout_id': layout.id,
            'campaign_id': layout.campaign_id,
            'slide_id': layout.slide_id,
            'format': layout.format,
            'dimensions': {'width': w, 'height': h},
            'proportions_verified': self.validate_proportions(layout.format),
            'safe_areas': self.get_safe_area(layout.format),
            'exact_texts': {
                'headline': layout.headline.text,
                'cta': layout.cta.text,
                'brand_name': layout.logo.brand_name,
                'decorative_label': layout.decorative.label,
            },
            'elements': layout.to_dict()['elements'],
            'svg': self.render_svg(layout, show_safe_areas=False),
        }

