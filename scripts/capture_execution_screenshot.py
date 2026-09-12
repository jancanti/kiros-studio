"""Script para captura de screenshots de evidência para M05 (Fila, Execução e Monitoramento)."""
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
    # Inicializa aplicação no diretório .kiros
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
            provenance=Provenance('user', 'scripts.capture_execution_screenshot', '2026-09-12T12:00:00+00:00'),
        )
        app.campaigns.add_storyboard_slide(target_cid, 'Slide 1: Ambiente Acolhedor', 'Vela acesa sobre aparador de madeira')
        app.campaigns.add_storyboard_slide(target_cid, 'Slide 2: Detalhe do Vidro', 'Close-up macro do vidro âmbar')
        app.campaigns.submit_for_approval(target_cid)
        app.campaigns.approve_campaign(target_cid, approver='Diretoria de Arte')

    camp = app.campaigns.get_campaign(target_cid)
    if camp.status == 'approved':
        app.campaigns.queue_execution(target_cid)
        # Executa 1 trabalho para mostrar progresso
        app.worker.run_once()

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
        desktop_png = ROOT / "docs/evidence/M05-desktop.png"
        mobile_png = ROOT / "docs/evidence/M05-mobile.png"

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

