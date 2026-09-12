"""Script para captura de screenshots de evidência para M04 (Campanhas, Storyboard e Tela de Aprovação)."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kiros.application import Application
from kiros.core.contracts import Provenance


def main():
    # Inicializa aplicação no diretório .kiros e cria uma campanha de demonstração para a tela de aprovação
    data_dir = ROOT / ".kiros"
    app = Application(data_dir)
    campaigns = app.campaigns.list_campaigns()

    target_cid = None
    for c in campaigns:
        if 'Aromas' in c['title'] or 'Outono' in c['title']:
            target_cid = c['id']
            break

    if not target_cid:
        briefing = {
            'primary_objective': 'lançamento',
            'secondary_objective': 'awareness',
            'summary': 'Lançamento da Vela Aromática Alecrim & Flor de Laranjeira em vidro âmbar com cera vegetal de coco.',
            'visual_tone': 'Acolhedor, minimalista e nórdico, luz natural suave e sombras quentes.',
            'confidence': 0.94,
        }
        strategy = {'funnel_stage': 'Descoberta', 'pillar': 'produtos'}
        products = [{'product_id': 'vela-alecrim', 'name': 'Vela Alecrim & Algodão'}]

        target_cid = app.campaigns.create_campaign(
            title='Velas de Outono 2026',
            briefing=briefing,
            strategy=strategy,
            products=products,
            approval_mode='minimal',
            provenance=Provenance('user', 'scripts.capture_campaigns_screenshot', '2026-09-12T12:00:00+00:00'),
        )

        app.campaigns.add_storyboard_slide(
            campaign_id=target_cid,
            title='Slide 1: Ritual da Manhã',
            visual_prompt='Vela acesa sobre aparador de carvalho claro com caneca de cerâmica e livro aberto.',
            framing='wide',
            caption_draft='Comece o dia com serenidade e o aroma fresco do alecrim.',
            engine_override='gemini:imagen-3.0-generate-002',
        )
        app.campaigns.add_storyboard_slide(
            campaign_id=target_cid,
            title='Slide 2: Detalhe do Vidro Âmbar',
            visual_prompt='Close-up macro na chama dourada e na cera líquida derretida no frasco âmbar.',
            framing='detail',
            caption_draft='Cera 100% vegetal com queima limpa e pavio de algodão trançado.',
            engine_override='openai:dall-e-3',
        )
        app.campaigns.add_storyboard_slide(
            campaign_id=target_cid,
            title='Slide 3: Composição no Lavabo',
            visual_prompt='Vela sobre bandeja de mármore travertino ao lado de toalhas de linho cru.',
            framing='medium',
            caption_draft='Elegância sutil e presença sensorial para qualquer ambiente.',
            engine_override='adobe:firefly-image-3',
        )

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
        url = f'http://127.0.0.1:8765/conteudo?campaign_id={target_cid}'
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200

        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        desktop_png = ROOT / "docs/evidence/M04-desktop.png"
        mobile_png = ROOT / "docs/evidence/M04-mobile.png"

        # Desktop screenshot
        subprocess.run([
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--screenshot={desktop_png}",
            "--window-size=1280,1200",
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
            "--window-size=390,1000",
            url,
        ], check=True)
        print(f"Capturado: {mobile_png} ({mobile_png.stat().st_size} bytes)")

    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == '__main__':
    main()

