"""Script para captura de screenshots e evidências visuais para M09 (Calendário e Instagram controlado)."""
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

    # Popula dados de demonstração no calendário se estiver vazio
    entries = app.calendar.list_entries()
    if not entries:
        # Entrada 1: Lançamento com recomendação aceita
        e1 = app.calendar.create_entry(
            title='Lançamento Difusor Lavanda Real & Âmbar',
            content_type='feed',
            pillar='lancamento',
            priority='high',
            scheduled_for='2026-10-14T19:30:00+00:00',
            notes='Post sensorial de topo/meio de funil destacando notas aromáticas suaves para desacelerar.',
        )
        rec1 = app.calendar.recommend_for_entry(e1.id)
        app.calendar.record_time_decision(e1.id, rec1.recommended_time, accept_recommendation=True)

        # Entrada 2: Post educativo
        e2 = app.calendar.create_entry(
            title='Guia Prático: Como Prolongar a Vida Útil das Velas',
            content_type='carousel',
            pillar='educativo',
            priority='medium',
            scheduled_for='2026-10-16T18:45:00+00:00',
            notes='Carrossel de 4 slides explicando queima uniforme e corte do pavio de algodão.',
        )
        rec2 = app.calendar.recommend_for_entry(e2.id)
        app.calendar.record_time_decision(e2.id, rec2.recommended_time, accept_recommendation=True)

        # Entrada 3: Post institucional / Sazonal
        e3 = app.calendar.create_entry(
            title='Primavera dos Aromas: Flores Brancas e Alecrim',
            content_type='feed',
            pillar='institucional',
            priority='medium',
            seasonal_tag='primavera_2026',
            phase='consideracao',
            scheduled_for='2026-10-18T19:00:00+00:00',
            notes='Harmonia de elementos botânicos naturais e raízes de Sorocaba.',
        )
        rec3 = app.calendar.recommend_for_entry(e3.id)
        app.calendar.record_time_decision(e3.id, '2026-10-18T20:15:00+00:00', accept_recommendation=False)

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
        url = 'http://127.0.0.1:8765/calendario'
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200

        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        desktop_png = ROOT / "docs/evidence/M09-desktop.png"
        mobile_png = ROOT / "docs/evidence/M09-mobile.png"

        # Desktop screenshot
        subprocess.run([
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--screenshot={desktop_png}",
            "--window-size=1280,2000",
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
            "--window-size=390,1600",
            url,
        ], check=True)
        print(f"Capturado: {mobile_png} ({mobile_png.stat().st_size} bytes)")

    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == '__main__':
    main()

