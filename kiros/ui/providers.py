"""Interface de configuração e testes de provedores de imagem."""
from html import escape
from typing import Any, Dict
from urllib.parse import urlencode

from kiros.application import Application
from kiros.providers.catalog import OFFICIAL_CATALOG


def dispatch_provider_action(app: Application, action: str, data: Dict[str, str]) -> str:
    """Executa ações de provider enviadas via POST."""
    pm = app.providers
    if action == 'save':
        pid = data.get('provider_id', '').strip()
        ptype = data.get('provider_type', '').strip()
        name = data.get('name', '').strip()
        model = data.get('model', '').strip()
        endpoint = data.get('endpoint', '').strip()
        secret = data.get('secret', '').strip()
        is_active = data.get('is_active') == '1'

        if not pid or not ptype or not model:
            raise ValueError('ID, tipo e modelo são campos obrigatórios.')

        existing = pm.get_provider(pid, include_secret=True)
        if existing:
            pm.update_provider(
                pid,
                name=name,
                model=model,
                endpoint=endpoint,
                secret=secret if secret else None,
                is_active=is_active,
            )
            return urlencode({'tab': 'providers', 'saved': '1', 'msg': f"Provedor '{pid}' atualizado."})
        else:
            pm.add_provider(
                pid,
                ptype,
                name=name,
                model=model,
                endpoint=endpoint,
                secret=secret if secret else None,
                is_active=is_active,
            )
            return urlencode({'tab': 'providers', 'saved': '1', 'msg': f"Provedor '{pid}' adicionado."})

    elif action == 'toggle':
        pid = data.get('provider_id', '').strip()
        is_active = data.get('is_active') == '1'
        pm.toggle_provider(pid, is_active)
        state_txt = 'ativado' if is_active else 'desativado'
        return urlencode({'tab': 'providers', 'msg': f"Provedor '{pid}' {state_txt}."})

    elif action == 'delete':
        pid = data.get('provider_id', '').strip()
        pm.delete_provider(pid)
        return urlencode({'tab': 'providers', 'msg': f"Provedor '{pid}' excluído."})

    elif action == 'test_connection':
        pid = data.get('provider_id', '').strip()
        res = pm.test_connection(pid)
        return urlencode({
            'tab': 'providers',
            'test_done': '1',
            'test_type': 'Conexão',
            'test_status': res.get('status', 'error'),
            'test_latency': str(res.get('latency_ms', 0)),
            'test_msg': res.get('message', ''),
        })

    elif action == 'test_simple':
        pid = data.get('provider_id', '').strip()
        res = pm.test_simple(pid)
        return urlencode({
            'tab': 'providers',
            'test_done': '1',
            'test_type': 'Geração simples',
            'test_status': res.get('status', 'error'),
            'test_latency': str(res.get('latency_ms', 0)),
            'test_msg': res.get('message', ''),
        })

    raise ValueError(f"Ação desconhecida: {action}")


def render_providers_panel(app: Application, query: Dict[str, Any]) -> str:
    """Renderiza painel simples, destilado e didático para provedores de IA e Instagram."""
    pm = app.providers
    providers = pm.list_providers()
    test_logs = pm.get_test_logs(limit=10)

    html = []

    # Wizard de Boas-Vindas / Instalação Guiada Compacto
    html.append('''
    <div class="panel onboarding-wizard-panel" style="background: linear-gradient(135deg, rgba(105,62,223,0.06) 0%, rgba(69,20,166,0.02) 100%); border: 1px solid var(--hairline-cool, #e4edf1); border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div>
                <span class="tag" style="background: #693edf; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">PASSOS INICIAIS</span>
                <h3 style="margin: 6px 0 2px; font-size: 17px;">👋 Bem-vindo às Configurações do KIROS Studio!</h3>
                <p style="color: #555; font-size: 13px; margin: 0;">Conecte seus motores de IA para gerar imagens e agendar posts para @usekiros.</p>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <span class="badge" style="background:#eef2ff; color:#693edf; border:1px solid #c7d2fe; font-size:12px; padding:4px 10px;">1. IA (Firefly, ChatGPT, Gemini)</span>
                <span class="badge" style="background:#eef2ff; color:#693edf; border:1px solid #c7d2fe; font-size:12px; padding:4px 10px;">2. Fallback Ativo</span>
                <span class="badge" style="background:#eef2ff; color:#693edf; border:1px solid #c7d2fe; font-size:12px; padding:4px 10px;">3. Instagram Graph</span>
            </div>
        </div>
    </div>
    ''')

    # Guia Rápido: Como encontrar suas chaves (Gaveta retrátil)
    guide_open_attr = 'open' if not providers else ''
    html.append(f'''
    <details class="panel" style="margin-bottom: 20px;" {guide_open_attr}>
        <summary style="font-size: 15px; font-weight: 600; cursor: pointer; color: var(--ink);">
            💡 Como pegar sua chave de API em 3 cliques
        </summary>
        <p style="color: #5d5d5d; font-size: 13px; margin: 12px 0 16px;">Consulte as instruções abaixo para cadastrar suas credenciais sem complicação:</p>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px;">
            <div style="border-left: 3px solid #e00000; background: #fafafa; padding: 12px; border-radius: 0 6px 6px 0;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px;">🎨 Adobe Firefly Services</h4>
                <ol style="margin: 0; padding-left: 18px; font-size: 12px; color: #444;">
                    <li>Acesse <a href="https://developer.adobe.com/console" target="_blank" rel="noopener">Adobe Developer Console</a></li>
                    <li>Crie um projeto de Firefly Services</li>
                    <li>Copie o Client ID e Secret obtidos</li>
                </ol>
            </div>
            <div style="border-left: 3px solid #10a37f; background: #fafafa; padding: 12px; border-radius: 0 6px 6px 0;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px;">🤖 ChatGPT (OpenAI / DALL-E)</h4>
                <ol style="margin: 0; padding-left: 18px; font-size: 12px; color: #444;">
                    <li>Acesse <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI API Keys</a></li>
                    <li>Clique em <em>Create new secret key</em></li>
                    <li>Copie a chave gerada (inicia com <code>sk-</code>)</li>
                </ol>
            </div>
            <div style="border-left: 3px solid #4285f4; background: #fafafa; padding: 12px; border-radius: 0 6px 6px 0;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px;">✨ Google Gemini / Imagen</h4>
                <ol style="margin: 0; padding-left: 18px; font-size: 12px; color: #444;">
                    <li>Acesse <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">Google AI Studio</a></li>
                    <li>Clique em <em>Get API key</em></li>
                    <li>Copie sua chave de API do Gemini</li>
                </ol>
            </div>
            <div style="border-left: 3px solid #e1306c; background: #fafafa; padding: 12px; border-radius: 0 6px 6px 0;">
                <h4 style="margin: 0 0 6px 0; font-size: 14px;">📸 Instagram Graph API</h4>
                <ol style="margin: 0; padding-left: 18px; font-size: 12px; color: #444;">
                    <li>Acesse Meta for Developers</li>
                    <li>Vincule sua página do Instagram (@usekiros)</li>
                    <li>Obtenha o User Access Token de publicação</li>
                </ol>
            </div>
        </div>
    </details>
    ''')

    # Avisos e resultados de teste
    if query.get('msg'):
        html.append(f'<p role="status" class="notice">{escape(query["msg"][0])}</p>')
    if query.get('saved'):
        html.append('<p role="status" class="notice">Configuração salva com segurança. Credenciais nunca são expostas.</p>')
    if query.get('test_done'):
        t_type = escape(query.get('test_type', ['Teste'])[0])
        t_status = escape(query.get('test_status', ['error'])[0])
        t_lat = escape(query.get('test_latency', ['0'])[0])
        t_msg = escape(query.get('test_msg', [''])[0])
        is_ok = t_status == 'ok'
        badge_class = 'badge-success' if is_ok else 'badge-error'
        badge_text = 'Sucesso' if is_ok else 'Erro'

        html.append(f'''
        <div class="panel test-result-panel" role="region" aria-label="Resultado do teste" style="margin-bottom: 20px;">
            <span class="tag {badge_class}">{badge_text}</span>
            <h3 style="margin: 6px 0;">Resultado do Teste: {t_type}</h3>
            <p style="font-size: 13px; margin: 2px 0;"><strong>Status:</strong> {t_status.upper()} | <strong>Latência:</strong> {t_lat} ms</p>
            <p style="font-size: 13px; margin: 2px 0;"><strong>Mensagem:</strong> {t_msg}</p>
        </div>
        ''')

    # Seção 1: Provedores cadastrados
    html.append('''
    <div class="panel" style="margin-bottom: 20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
            <div>
                <span class="tag">Motores de Imagem</span>
                <h2 style="margin: 4px 0 0;">Provedores Configurados</h2>
            </div>
        </div>
    ''')

    if not providers:
        html.append('<p class="empty-state" style="margin-top:8px;">Nenhum provedor configurado ainda. Utilize o formulário abaixo para adicionar seu primeiro motor de IA (Adobe Firefly, ChatGPT ou Gemini).</p>')
    else:
        html.append('<div class="provider-cards">')
        for p in providers:
            pid = escape(p['id'])
            pname = escape(p['name'])
            ptype = escape(p['type'].upper())
            pmodel = escape(p['model'])
            pendpoint = escape(p['endpoint'])
            pactive = p['is_active']
            status_text = 'Ativo' if pactive else 'Inativo'
            status_class = 'status-active' if pactive else 'status-inactive'
            secret_preview = escape(p['secret_preview'])

            html.append(f'''
            <div class="card provider-card">
                <div class="card-header">
                    <div>
                        <span class="tag">{ptype}</span>
                        <h3>{pname} <small>({pid})</small></h3>
                    </div>
                    <span class="badge {status_class}">{status_text}</span>
                </div>
                <div class="card-body">
                    <p><strong>Modelo:</strong> <code>{pmodel}</code></p>
                    <p><strong>Endpoint:</strong> <code>{pendpoint}</code></p>
                    <p><strong>Credencial:</strong> <span class="secret-shield">{secret_preview}</span></p>
                </div>
                <div class="card-actions">
                    <form method="post" action="/api/providers/toggle" class="inline-form">
                        <input type="hidden" name="provider_id" value="{pid}">
                        <input type="hidden" name="is_active" value="{'0' if pactive else '1'}">
                        <button type="submit" class="button-secondary">{'Desativar' if pactive else 'Ativar'}</button>
                    </form>
                    <form method="post" action="/api/providers/test_connection" class="inline-form">
                        <input type="hidden" name="provider_id" value="{pid}">
                        <button type="submit" class="button-secondary">Testar conexão</button>
                    </form>
                    <form method="post" action="/api/providers/test_simple" class="inline-form">
                        <input type="hidden" name="provider_id" value="{pid}">
                        <button type="submit" class="button-secondary">Teste simples</button>
                    </form>
                    <form method="post" action="/api/providers/delete" class="inline-form" onsubmit="return confirm('Excluir este provedor?');">
                        <input type="hidden" name="provider_id" value="{pid}">
                        <button type="submit" class="button-danger">Excluir</button>
                    </form>
                </div>
            </div>
            ''')
        html.append('</div>')
    html.append('</div>')

    # Seção 2: Adicionar / Editar Provedor (Aberto por padrão)
    form_open_attr = 'open'
    html.append(f'''
    <details class="panel" style="margin-bottom: 20px;" {form_open_attr}>
        <summary style="font-size: 16px; font-weight: 600; cursor: pointer; color: var(--ink);">
            ➕ Adicionar ou Atualizar Provedor
        </summary>
        <p style="color: #5d5d5d; font-size: 13px; margin: 8px 0 16px;">Cadastre adaptadores oficiais da especificação (Gemini, OpenAI, Firefly) ou provedor customizado. Nenhum modelo inexistente ou presumido é aceito.</p>
        <form method="post" action="/api/providers/save" class="form-grid">
            <div class="form-group">
                <label for="p_id">Identificador único (ID)</label>
                <input id="p_id" name="provider_id" placeholder="ex: gemini-principal" maxlength="64" required>
            </div>
            <div class="form-group">
                <label for="p_name">Nome de exibição</label>
                <input id="p_name" name="name" placeholder="ex: Google Gemini (Imagen 3)" maxlength="80">
            </div>
            <div class="form-group">
                <label for="p_type">Tipo de Provedor</label>
                <select id="p_type" name="provider_type" required>
                    <option value="gemini">Google Gemini (Imagen 3)</option>
                    <option value="openai">OpenAI (DALL-E)</option>
                    <option value="firefly">Adobe Firefly Services</option>
                    <option value="custom">Custom Image Provider (Auto-hospedado)</option>
                </select>
            </div>
            <div class="form-group">
                <label for="p_model">Modelo</label>
                <input id="p_model" name="model" value="imagen-3.0-generate-002" required list="known-models">
                <datalist id="known-models">
                    <option value="imagen-3.0-generate-002">Imagen 3 (Padrão Google)</option>
                    <option value="imagen-3.0-fast-generate-001">Imagen 3 Fast (Google)</option>
                    <option value="dall-e-3">DALL-E 3 (OpenAI)</option>
                    <option value="dall-e-2">DALL-E 2 (OpenAI)</option>
                    <option value="firefly-image-3">Firefly Image 3 (Adobe)</option>
                    <option value="firefly-image-2">Firefly Image 2 (Adobe)</option>
                </datalist>
                <small class="hint">Modelos oficiais verificados em 2026-09-12.</small>
            </div>
            <div class="form-group">
                <label for="p_endpoint">Endpoint (Opcional se tipo oficial)</label>
                <input id="p_endpoint" name="endpoint" placeholder="Deixe em branco para usar o endpoint oficial">
            </div>
            <div class="form-group">
                <label for="p_secret" style="display: block; margin-bottom: 6px;">Chave de API / Segredo</label>
                <input id="p_secret" name="secret" type="password" placeholder="Digite a chave da API (armazenada de forma segura)" style="display: block; width: 100%; max-width: 440px;">
                <div class="hint" style="display: block; width: 100%; margin-top: 6px; margin-bottom: 10px; font-size: 12px; color: var(--muted-blue);">
                    A chave nunca será reexibida após o salvamento.
                </div>
                <div style="display: block; margin-top: 4px;">
                    <label class="checkbox-inline" style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500; cursor: pointer;">
                        <input type="checkbox" name="is_active" value="1" checked style="width: 16px !important; height: 16px !important; margin: 0 !important; cursor: pointer;">
                        <span>Provedor ativo para roteamento</span>
                    </label>
                </div>
            </div>
            <button type="submit" class="button">Salvar Provedor</button>
        </form>
    </details>
    ''')

    # Seção 3 & 4: Telemetria do Roteador & Histórico de Testes (Gaveta Retrátil)
    rec = app.router.recommend()
    html.append(f'''
    <details class="panel" style="margin-bottom: 20px;">
        <summary style="font-size: 15px; font-weight: 600; cursor: pointer; color: var(--ink);">
            📊 Telemetria do Roteador &amp; Histórico de Testes
        </summary>
        <div style="margin-top: 16px;">
            <span class="tag">Roteador de Motores</span>
            <h3 style="margin: 4px 0 8px;">Recomendação Automática de Motor</h3>
            <p style="font-size: 13px; color: #555;">O <code>ImageEngineRouter</code> avalia a tarefa do slide e sugere o motor mais eficiente. Decisões manuais sempre prevalecem.</p>
            <div class="recommendation-box" style="margin-bottom: 20px;">
                <p><strong>Motor Recomendado:</strong> {rec['provider'].upper()} — <code>{rec['model']}</code></p>
                <p><strong>Motivo:</strong> {rec['reason']}</p>
                <p><strong>Custo estimado por imagem:</strong> ${rec['estimated_cost']:.4f}</p>
                <p><strong>Confiança do roteador:</strong> {int(rec['confidence'] * 100)}%</p>
                <h4 style="margin-top: 8px;">Alternativas avaliadas:</h4>
                <ul>
    ''')
    for alt in rec.get('alternatives', []):
        html.append(f'''
            <li><strong>{alt['provider'].upper()}</strong> (<code>{alt['model']}</code>) — ${alt['estimated_cost']:.4f} ({int(alt['confidence']*100)}% confiança): {alt['reason']}</li>
        ''')
    html.append('''
                </ul>
            </div>
    ''')

    if test_logs:
        html.append('''
            <h3 style="margin: 16px 0 8px;">Histórico Recente de Testes</h3>
            <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Provedor</th>
                        <th>Tipo de Teste</th>
                        <th>Status</th>
                        <th>Latência</th>
                        <th>Mensagem</th>
                        <th>Data/Hora</th>
                    </tr>
                </thead>
                <tbody>
        ''')
        for log in test_logs:
            st = escape(log['status'])
            st_badge = 'badge-success' if st == 'ok' else 'badge-error'
            html.append(f'''
                <tr>
                    <td><code>{escape(log['provider_id'])}</code></td>
                    <td>{escape(log['test_type'])}</td>
                    <td><span class="tag {st_badge}">{st}</span></td>
                    <td>{log['latency_ms']} ms</td>
                    <td>{escape(log['message'])}</td>
                    <td><small>{escape(log['executed_at'][:19].replace('T', ' '))}</small></td>
                </tr>
            ''')
        html.append('''
                </tbody>
            </table>
            </div>
        ''')

    html.append('''
        </div>
    </details>
    ''')

    return '\n'.join(html)


