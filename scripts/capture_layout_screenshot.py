"""Script para captura de screenshots e evidências visuais para M07 (Layout determinístico e editor)."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kiros.application import Application
from kiros.core.contracts import Provenance


def main():
    data_dir = ROOT / ".kiros"
    app = Application(data_dir)
    campaigns = app.campaigns.list_campaigns()

    target_cid = None
    for c in campaigns:
        if c['title'].startswith('Velas de Outono'):
            target_cid = c['id']
            break

    if not target_cid:
        target_cid = app.campaigns.create_campaign(
            title='Velas de Outono 2026',
            briefing={'primary_objective': 'lançamento', 'summary': 'Coleção de velas em vidro âmbar'},
            strategy={'funnel_stage': 'Descoberta'},
            products=[{'product_id': 'vela-alecrim', 'name': 'Vela Alecrim & Algodão'}],
            approval_mode='minimal',
            provenance=Provenance('user', 'scripts.capture_layout_screenshot', '2026-09-12T14:00:00+00:00'),
        )
        app.campaigns.add_storyboard_slide(target_cid, 'Slide 1: Ambiente Acolhedor', 'Vela acesa sobre aparador de madeira')
        app.campaigns.add_storyboard_slide(target_cid, 'Slide 2: Detalhe do Vidro', 'Close-up macro do vidro âmbar')

    camp = app.campaigns.get_campaign(target_cid)
    slides = camp.slides
    s1_id = slides[0].id

    # Garante que o slide 1 possui layout
    layout_4x5 = app.campaigns.get_slide_layout(s1_id)
    if not layout_4x5:
        layout_4x5 = app.campaigns.create_default_layout(s1_id, layout_format="4:5")

    # Gera evidência visual SVG em 4:5
    svg_4x5 = app.layout_engine.render_svg(layout_4x5, show_safe_areas=True)
    svg_4x5_path = ROOT / "docs/evidence/M07-layout-4x5.svg"
    svg_4x5_path.write_text(svg_4x5, encoding="utf-8")
    print(f"Salvo: {svg_4x5_path} ({len(svg_4x5)} bytes)")

    # Adapta para 9:16 e salva evidência visual SVG em 9:16
    layout_9x16 = app.layout_engine.adapt_format(layout_4x5, "9:16")
    svg_9x16 = app.layout_engine.render_svg(layout_9x16, show_safe_areas=True)
    svg_9x16_path = ROOT / "docs/evidence/M07-layout-9x16.svg"
    svg_9x16_path.write_text(svg_9x16, encoding="utf-8")
    print(f"Salvo: {svg_9x16_path} ({len(svg_9x16)} bytes)")

    # Inicia o servidor kiros na porta 8765
    server = subprocess.Popen(
        [sys.executable, '-m', 'kiros', '--port', '8765', '--data-dir', '.kiros'],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(1.5)

    try:
        url = f'http://127.0.0.1:8765/conteudo?campaign_id={target_cid}&editor_slide_id={s1_id}'
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200

        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        desktop_png = ROOT / "docs/evidence/M07-desktop.png"
        mobile_png = ROOT / "docs/evidence/M07-mobile.png"

        # Desktop screenshot
        subprocess.run([
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--screenshot={desktop_png}",
            "--window-size=1280,1600",
            url,
        ], check=True)
        print(f"Capturado: {desktop_png} ({desktop_png.stat().st_size} bytes)")

        # Mobile screenshot
        subprocess.run([
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--screenshot={mobile_png}",
            "--window-size=390,1400",
            url,
        ], check=True)
        print(f"Capturado: {mobile_png} ({mobile_png.stat().st_size} bytes)")

    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == '__main__':
    main()

