import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode
from email.parser import BytesParser
from email.policy import default
from kiros.ui.library import dispatch
from kiros.application import Application, NAVIGATION
from kiros.ui.page import render_page


def make_server(data_dir, port=8765):
    app = Application(Path(data_dir))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Não registrar URLs, payloads ou credenciais.

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def respond(self, code, body, kind='text/html; charset=utf-8', location=None):
            data = body if isinstance(body, bytes) else body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            if location:
                self.send_header('Location', location)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, 'Host não permitido')
            path = urlsplit(self.path).path
            if path == '/api/health':
                return self.respond(200, json.dumps(app.status()), 'application/json')
            if path == '/style.css':
                return self.respond(200, (Path(__file__).parent / 'ui/style.css').read_text(), 'text/css')
            if path.startswith('/assets/'):
                ref_id = path.removeprefix('/assets/')
                with app.library.connection() as db:
                    row = db.execute('SELECT asset_key,mime FROM visual_references WHERE id=?', (ref_id,)).fetchone()
                if not row:
                    return self.respond(404, 'Imagem não encontrada')
                return self.respond(200, app.storage.get(row['asset_key']), row['mime'])
            if path == '/api/layout/svg':
                query = parse_qs(urlsplit(self.path).query)
                lid = query.get('layout_id', [''])[0]
                safe = query.get('safe_areas', ['0'])[0] == '1'
                if not lid:
                    return self.respond(400, 'layout_id é obrigatório')
                try:
                    svg_content = app.campaigns.render_slide_svg(lid, show_safe_areas=safe)
                    return self.respond(200, svg_content, 'image/svg+xml; charset=utf-8')
                except Exception as exc:
                    return self.respond(404, str(exc))
            if path == '/api/layout/export':
                query = parse_qs(urlsplit(self.path).query)
                lid = query.get('layout_id', [''])[0]
                if not lid:
                    return self.respond(400, 'layout_id é obrigatório')
                try:
                    export_data = app.campaigns.export_slide_layout(lid)
                    return self.respond(200, json.dumps(export_data, ensure_ascii=False), 'application/json')
                except Exception as exc:
                    return self.respond(404, str(exc))
            if path == '/api/content/audit':
                query = parse_qs(urlsplit(self.path).query)
                sid = query.get('slide_id', [''])[0]
                cid = query.get('campaign_id', [''])[0]
                seq_id = query.get('sequence_id', [''])[0]
                try:
                    if sid:
                        res = app.campaigns.audit_slide_pre_publish(sid)
                        return self.respond(200, json.dumps(res.to_dict(), ensure_ascii=False), 'application/json')
                    elif seq_id:
                        res = app.campaigns.audit_story_sequence_pre_publish(seq_id)
                        return self.respond(200, json.dumps(res.to_dict(), ensure_ascii=False), 'application/json')
                    elif cid:
                        res = app.campaigns.audit_campaign_pre_publish(cid)
                        return self.respond(200, json.dumps(res, ensure_ascii=False), 'application/json')
                    return self.respond(400, 'Informe slide_id, sequence_id ou campaign_id')
                except Exception as exc:
                    return self.respond(404, str(exc))
            if path == '/api/calendar/entries':
                try:
                    entries = [e.to_dict() for e in app.calendar.list_entries()]
                    return self.respond(200, json.dumps(entries, ensure_ascii=False), 'application/json')
                except Exception as exc:
                    return self.respond(500, str(exc))
            section = path.strip('/') or 'inicio'
            if section not in dict(NAVIGATION):
                return self.respond(404, 'Página não encontrada')
            return self.respond(200, render_page(app, section, urlsplit(self.path).query == 'saved=1', parse_qs(urlsplit(self.path).query)))

        def do_POST(self):
            origin = self.headers.get('Origin')
            expected = f'http://{self.headers.get("Host")}'
            if not self.valid_host() or origin != expected or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.respond(403, 'Origem não permitida')
            if self.path.startswith('/api/library/'):
                action = self.path.rsplit('/', 1)[-1]
                section = 'biblioteca' if action in ('reference', 'analyze') else 'marca'
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 6_000_000:
                        raise ValueError('Envio vazio ou maior que 6 MB.')
                    raw = self.rfile.read(size)
                    content_type = self.headers.get('Content-Type', '')
                    data, uploads = {}, {}
                    if content_type.split(';')[0] == 'application/x-www-form-urlencoded':
                        parsed = parse_qs(raw.decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=100)
                        if any(len(v) != 1 for v in parsed.values()):
                            raise ValueError('Campos duplicados.')
                        data = {k: v[0] for k, v in parsed.items()}
                    elif content_type.split(';')[0] == 'multipart/form-data':
                        message = BytesParser(policy=default).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw)
                        if not message.is_multipart() or message.defects:
                            raise ValueError('Envio de arquivo inválido.')
                        for part in message.iter_parts():
                            key = part.get_param('name', header='content-disposition')
                            if not key or key in data or key in uploads or part.is_multipart() or part.defects:
                                raise ValueError('Campo de arquivo inválido ou duplicado.')
                            value = part.get_payload(decode=True)
                            if part.get_filename() is not None:
                                uploads[key] = value
                            else:
                                data[key] = value.decode('utf-8')
                    else:
                        return self.respond(415, 'Formato não permitido')
                    section = dispatch(app.library, action, data, uploads)
                except UnicodeError:
                    return self.respond(303, '', location='/' + section + '?' + urlencode({'error': 'Use texto ou CSV em UTF-8.'}))
                except ValueError as exc:
                    return self.respond(303, '', location='/' + section + '?' + urlencode({'error': str(exc)}))
                return self.respond(303, '', location='/' + section + '?saved=1')
            if self.path.startswith('/api/providers/'):
                from kiros.ui.providers import dispatch_provider_action
                action = self.path.rsplit('/', 1)[-1]
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    return self.respond(415, 'Formato não permitido')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 64000:
                        raise ValueError('Tamanho de requisição inválido.')
                    parsed = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=50)
                    data = {k: v[0] for k, v in parsed.items()}
                    query_str = dispatch_provider_action(app, action, data)
                    return self.respond(303, '', location='/configuracoes?' + query_str)
                except (ValueError, UnicodeError) as exc:
                    return self.respond(303, '', location='/configuracoes?' + urlencode({'tab': 'providers', 'error': str(exc)}))
            if self.path.startswith('/api/creator/'):
                from kiros.ui.creator import dispatch_creator_action
                action = self.path.rsplit('/', 1)[-1]
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    return self.respond(415, 'Formato não permitido')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 64000:
                        raise ValueError('Tamanho de requisição inválido.')
                    parsed = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=50)
                    data = {k: v[0] for k, v in parsed.items()}
                    query_str = dispatch_creator_action(app, action, data)
                    return self.respond(303, '', location='/criar?' + query_str)
                except (ValueError, UnicodeError) as exc:
                    return self.respond(303, '', location='/criar?' + urlencode({'error': str(exc)}))
            if self.path.startswith('/api/campaigns/'):
                from kiros.ui.campaigns import dispatch_campaign_action
                action = self.path.rsplit('/', 1)[-1]
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    return self.respond(415, 'Formato não permitido')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 64000:
                        raise ValueError('Tamanho de requisição inválido.')
                    parsed = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=50)
                    data = {k: v[0] for k, v in parsed.items()}
                    query_str = dispatch_campaign_action(app, action, data)
                    return self.respond(303, '', location='/conteudo?' + query_str)
                except (ValueError, UnicodeError, PermissionError, Exception) as exc:
                    return self.respond(303, '', location='/conteudo?' + urlencode({'error': str(exc)}))
            if self.path.startswith('/api/calendar/'):
                from kiros.ui.calendar import dispatch_calendar_action
                action = self.path.rsplit('/', 1)[-1]
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    return self.respond(415, 'Formato não permitido')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 64000:
                        raise ValueError('Tamanho de requisição inválido.')
                    parsed = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=50)
                    data = {k: v[0] for k, v in parsed.items()}
                    query_str = dispatch_calendar_action(app, action, data)
                    return self.respond(303, '', location='/calendario?' + query_str)
                except (ValueError, UnicodeError, PermissionError, Exception) as exc:
                    return self.respond(303, '', location='/calendario?' + urlencode({'error': str(exc)}))
            if self.path != '/api/preferences':
                return self.respond(404, 'Operação não encontrada')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                return self.respond(415, 'Formato não permitido')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError()
                body = parse_qs(self.rfile.read(size).decode('utf-8'), strict_parsing=True)
                if set(body) != {'workspace_name'} or len(body['workspace_name']) != 1:
                    raise ValueError()
                app.rename_workspace(body['workspace_name'][0])
            except (ValueError, UnicodeError):
                return self.respond(400, 'Nome inválido. Use entre 1 e 80 caracteres.')
            return self.respond(303, '', location='/configuracoes?saved=1')

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='KIROS Studio local')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', default=os.getenv('KIROS_DATA_DIR', '.kiros'))
    args = parser.parse_args()
    os.umask(0o077)
    server = make_server(args.data_dir, args.port)
    print(f'KIROS Studio: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
