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
            content += '<p role="status" class="notice">Nome do espaço salvo neste dispositivo.</p>'
        if query and query.get('backup_created'):
            content += f'<p role="status" class="notice">Backup gerado com sucesso: {query["backup_created"][0]}</p>'
        content += f'''<div class="panel"><h2>Seu espaço</h2>
        <p>Este nome identifica o espaço local. A identidade oficial da marca é preservada.</p>
        <form method="post" action="/api/preferences">
        <label for="workspace">Nome do espaço</label>
        <input id="workspace" name="workspace_name" value="{name}" maxlength="80" required>
        <button type="submit">Salvar nome</button></form></div>
        <div class="note"><h2>Simulação local</h2>
        <p>Nenhuma IA externa está conectada. Geração e publicação reais exigem configuração explícita e autorização.</p></div>'''

        # Painel de Backup & Restauração (Seção 71 e M12-A01)
        backups = app.backup.list_backups()
        content += '''<div class="panel"><h2>Backup e Restauração (Seção 71)</h2>
        <p>O backup gera um snapshot atômico do SQLite, Brand Bible, Product Bible, campanhas, assets e configurações. <strong>O histórico nunca é apagado automaticamente.</strong></p>
        <form method="post" action="/api/backup/create"><button type="submit">Gerar Novo Backup Agora</button></form>'''
        if backups:
            content += '<h3>Backups disponíveis neste dispositivo</h3><div class="table-scroll"><table><thead><tr><th>Arquivo</th><th>Data</th><th>Tamanho</th><th>Arquivos</th><th>Ações</th></tr></thead><tbody>'
            for b in backups:
                sz_kb = b['size_bytes'] / 1024
                date_str = b['created_at'][:19] if b['created_at'] else b['modified_at'][:19]
                content += f'<tr><td><strong>{b["name"]}</strong></td><td>{date_str}</td><td>{sz_kb:.1f} KB</td><td>{b["files_count"]}</td><td><a href="/api/backup/download?name={b["name"]}">Baixar ZIP</a></td></tr>'
            content += '</tbody></table></div>'
        else:
            content += '<p class="aside-note">Nenhum backup gerado ainda neste dispositivo.</p>'
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Rubik:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/style.css"></head>
    <body><a class="skip" href="#main">Pular para o conteúdo</a>
    <aside><a class="wordmark" href="/inicio" aria-label="KIROS Studio, início">KIROS<span>STUDIO</span></a>
    <nav aria-label="Navegação principal">{links}</nav>
    <p class="aside-note">Aromas para casa.<br>Presença com intenção.</p></aside>
    <div class="workspace"><header><span>{name}</span>
    <form class="header-command-bar" method="post" action="/api/command">
    <input id="head-cmd" type="text" name="command" placeholder="Command Bar (ex: 'Abra a última campanha')" required>
    <button type="submit">Executar</button></form>
    <span class="mode">Simulação local</span></header>
    <main id="main" tabindex="-1">{content}</main><footer>KIROS Aromas <span>Sorocaba · SP</span></footer></div></body></html>'''
