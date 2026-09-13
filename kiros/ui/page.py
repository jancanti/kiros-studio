from html import escape
from kiros.application import NAVIGATION

DESCRIPTIONS = {
    'criar': 'Briefings, estratégia e criação de conteúdo serão organizados aqui.',
    'calendario': 'Seu planejamento editorial terá um lugar próprio.',
    'conteudo': 'Campanhas e suas versões serão reunidas aqui.',
    'biblioteca': 'Ativos e referências visuais terão um acervo local.',
    'insights': 'Análises serão apresentadas com a origem dos dados.',
    'marca': 'A identidade oficial e os produtos terão um espaço de consulta.',
}


def render_page(app, section, saved=False, query=None):
    title = dict(NAVIGATION)[section]
    name = escape(app.status()['workspace_name'], quote=True)
    links = ''.join('<a href="/' + key + '"' + (' aria-current="page"' if key == section else '')
                    + '>' + label + '</a>' for key, label in NAVIGATION)
    if section == 'inicio':
        from kiros.ui.dashboard import render_dashboard
        content = render_dashboard(app, query or {})
    elif section in ('marca', 'biblioteca'):
        from kiros.ui.library import render_library
        content = render_library(app, section, query or {})
    elif section == 'criar':
        from kiros.ui.creator import render_creator
        content = render_creator(app, query or {})
    elif section == 'calendario':
        from kiros.ui.calendar import render_calendar
        content = render_calendar(app, query or {})
    elif section == 'insights':
        from kiros.ui.insights import render_insights
        content = render_insights(app, query or {})
    elif section == 'conteudo':
        from kiros.ui.campaigns import render_campaigns_hub
        content = render_campaigns_hub(app, query or {})
    elif section == 'configuracoes':
        from kiros.ui.providers import render_providers_panel
        content = '<p class="eyebrow">Preferências locais, Backup e Provedores</p><h1>Configurações</h1>'
        if saved:
            content += '<p role="status" class="notice">Configurações salvas com sucesso neste dispositivo.</p>'
        if query and query.get('backup_created'):
            content += f'<p role="status" class="notice">Backup gerado com sucesso: {escape(query["backup_created"][0])}</p>'

        # Painel Distil: Seu Espaço e Backup Unificados
        backups = app.backup.list_backups()
        content += f'''
        <div class="panel" style="margin-bottom:24px;max-width:900px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:20px;">
                <div style="flex:1;min-width:260px;">
                    <span class="tag">Espaço Local</span>
                    <h2 style="margin:4px 0 8px;">Seu Espaço de Trabalho</h2>
                    <form method="post" action="/api/preferences" class="inline-form" style="gap:8px;margin:0;align-items:center;">
                        <input id="workspace" name="workspace_name" value="{name}" maxlength="80" required style="max-width:260px;height:42px;padding:0 16px;box-sizing:border-box;font-size:14px;">
                        <button type="submit" class="button-secondary" style="margin:0;padding:0 18px;height:42px;min-height:42px;font-size:14px;font-weight:600;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;">Salvar Nome</button>
                    </form>
                </div>
                <div style="flex:1;min-width:260px;border-left:1px solid var(--hairline);padding-left:20px;">
                    <span class="tag">Segurança &amp; Backup</span>
                    <h2 style="margin:4px 0 8px;">Backup Atômico (Seção 71)</h2>
                    <form method="post" action="/api/backup/create" class="inline-form" style="margin:0;">
                        <button type="submit" class="button" style="margin:0;padding:6px 14px;font-size:13px;min-height:38px;">Gerar Backup Agora 💾</button>
                    </form>
                </div>
            </div>
            <div style="margin-top:14px;">
                <p class="aside-note" style="margin:0;font-size:12px;color:var(--muted);">Simulação local ativa: Nenhuma IA externa está conectada sem autorização explícita.</p>
        '''

        if backups:
            content += f'''
                <details style="margin-top:12px;padding:12px;background:var(--surface-input);border:1px solid var(--hairline-cool);border-radius:var(--radius-sm);">
                    <summary style="font-size:13px;font-weight:600;color:var(--ink);cursor:pointer;">
                        📁 Ver Backups Salvos Neste Dispositivo ({len(backups)})
                    </summary>
                    <div class="table-scroll" style="margin-top:12px;">
                        <table><thead><tr><th>Arquivo</th><th>Data</th><th>Tamanho</th><th>Arquivos</th><th>Ação</th></tr></thead><tbody>
            '''
            for b in backups:
                sz_kb = b['size_bytes'] / 1024
                date_str = b['created_at'][:19] if b['created_at'] else b['modified_at'][:19]
                content += f'<tr><td><strong>{escape(b["name"])}</strong></td><td>{date_str}</td><td>{sz_kb:.1f} KB</td><td>{b["files_count"]}</td><td><a href="/api/backup/download?name={escape(b["name"])}" class="button-secondary" style="padding:4px 8px;font-size:11px;text-decoration:none;">Baixar ZIP</a></td></tr>'
            content += '</tbody></table></div></details>'
        content += '</div>'

        content += render_providers_panel(app, query or {})
    else:
        content = f'''<p class="eyebrow">KIROS Studio</p><h1>{title}</h1>
        <div class="panel"><span class="tag">Ainda não disponível</span>
        <h2>{DESCRIPTIONS[section]}</h2><p>Esta etapa contém somente a navegação base do estúdio.</p>
        <a href="/inicio">Voltar ao início</a></div>'''
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} · KIROS Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Rubik:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/style.css"></head>
    <body><a class="skip" href="#main">Pular para o conteúdo</a>
    <aside><a class="wordmark" href="/inicio" aria-label="KIROS Studio, início">KIROS<span>STUDIO</span></a>
    <nav aria-label="Navegação principal">{links}</nav>
    <p class="aside-note">Aromas para casa.<br>Presença com intenção.</p></aside>
    <div class="workspace"><header><span>{name}</span>
    <form class="header-command-bar" method="post" action="/api/command">
    <input id="head-cmd" type="text" name="command" placeholder="Command Bar (ex: 'Abra a última campanha')" aria-label="Buscar comandos ou navegar" required>
    <button type="submit">Executar</button></form>
    <span class="mode">Simulação local</span></header>
    <main id="main" tabindex="-1">{content}</main><footer>KIROS Aromas <span>Sorocaba · SP</span></footer></div></body></html>'''
