"""Evidência M10 com fixtures explícitas e banco temporário; não altera .kiros."""
from datetime import timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kiros.application import Application
from kiros.__main__ import make_server


def main():
    with tempfile.TemporaryDirectory(prefix='kiros-m10-visual-') as temp:
        app = Application(Path(temp) / 'data')
        service = app.insights
        for i in range(3):
            service.record_diversity(f'Demonstração — composição {i + 1}',
                {'palette': 'Verde', 'framing': 'Plano aberto', 'pillar': 'Lifestyle'},
                (service.now() - timedelta(days=i + 1)).isoformat(),
                'Fixture simulada / M10', intentional_reason='Série de demonstração com unidade visual')
        service.record_competitor('Estúdio exemplo (fictício)', 'Decoração', 'Sorocaba',
            'Fixture local de demonstração — nenhum perfil externo consultado',
            (service.now() - timedelta(days=1)).isoformat(), 'Composições com materiais naturais.', {
                'trend': 'Texturas naturais', 'relevance': 'Afinidade com rituais da casa',
                'saturation': 'Desconhecida fora desta demonstração', 'copy_risk': 'Não reproduzir composições da fonte',
                'kiros_interpretation': 'Explorar texturas próprias em uma composição original',
                'potential': 'Hipótese visual a testar', 'confidence': 'Baixa — dados fictícios',
                'recommendation': 'Validar com referências reais antes de decidir'}, is_mock=True)
        eid = service.create_experiment('Demonstração: plano aberto muda a taxa de clique?',
            'Plano fechado', 'Plano aberto', 'framing', 'Visitas com clique',
            authorization='Autorização fictícia para demonstração local', operator='Demo')
        service.start_experiment(eid, 'Demo')
        service.record_result(eid, 12, 2, 12, 4, 'Fixture simulada; não são métricas reais', 'Demo')
        service.create_experiment('Demonstração: uma copy mais curta muda a resposta?',
            'Copy longa', 'Copy curta', 'copy', 'Visitas com clique')
        server = make_server(Path(temp) / 'data', 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            subprocess.run(['node', str(ROOT / 'scripts/capture_insights_browser.mjs'),
                            f'http://127.0.0.1:{server.server_port}', str(ROOT / 'docs/evidence')],
                           check=True, timeout=120)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    main()
