"""HTTP real e reinício de processos; apenas loopback e diretório temporário."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kiros.application import NAVIGATION


def start(directory):
    process = subprocess.Popen([sys.executable, '-m', 'kiros', '--port', '0', '--data-dir', directory],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               env={**os.environ, 'KIROS_PROVIDER_MODE': 'mock'})
    line = process.stdout.readline().strip()
    if not line.startswith('KIROS Studio: http://127.0.0.1:'):
        process.terminate()
        raise RuntimeError('Inicialização falhou: ' + process.stderr.read())
    return process, int(line.rsplit(':', 1)[1])


def request(port, path, method='GET', body=None, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    conn.request(method, path, body, headers or {})
    response = conn.getresponse()
    result = response.status, response.read().decode(), dict(response.getheaders())
    conn.close()
    return result


def stop(process):
    process.terminate()
    process.communicate(timeout=5)


with tempfile.TemporaryDirectory() as directory:
    process, port = start(directory)
    try:
        for key, label in NAVIGATION:
            status, page, headers = request(port, '/' + key)
            assert status == 200 and f'<title>{label} · KIROS Studio</title>' in page
            assert 'aria-current="page"' in page and 'Pular para o conteúdo' in page
            assert 'frame-ancestors' in headers['Content-Security-Policy']
        assert request(port, '/.env')[0] == 404
        assert request(port, '/api/health', headers={'Host': 'attacker.test'})[0] == 403
        payload = urlencode({'workspace_name': '<script>teste</script>'})
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        assert request(port, '/api/preferences', 'POST', payload, headers)[0] == 403
        headers['Origin'] = 'https://attacker.test'
        assert request(port, '/api/preferences', 'POST', payload, headers)[0] == 403
        headers['Origin'] = f'http://127.0.0.1:{port}'
        assert request(port, '/api/preferences', 'POST', payload, headers)[0] == 303
        assert request(port, '/api/preferences', 'POST', 'workspace_name=', headers)[0] == 400
        assert '&lt;script&gt;teste&lt;/script&gt;' in request(port, '/configuracoes')[1]
    finally:
        stop(process)
    # Filesystem escrito e lido em processos distintos também.
    setup = 'from pathlib import Path; from kiros.infrastructure.local import FileStorage; import sys; '
    subprocess.run([sys.executable, '-c', setup + "FileStorage(Path(sys.argv[1])).put('fixture.txt', b'local fixture')", directory + '/files'], cwd=ROOT, check=True)
    process, port = start(directory)
    try:
        assert json.loads(request(port, '/api/health')[1])['workspace_name'] == '<script>teste</script>'
        subprocess.run([sys.executable, '-c', setup + "assert FileStorage(Path(sys.argv[1])).get('fixture.txt') == b'local fixture'", directory + '/files'], cwd=ROOT, check=True)
    finally:
        stop(process)
print('Smoke aprovado: 8 rotas, validação HTTP, CSRF/Host, escape HTML, SQLite e arquivos após reinício.')
