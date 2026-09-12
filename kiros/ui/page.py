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
        content = '''<p class="eyebrow">Seu espaço de criação</p>
        <h1>Intenção antes<br>da criação.</h1>
        <p class="intro">Um estúdio para cuidar da presença da KIROS.<br>
        Da identidade ao conteúdo, com contexto e aprovação.</p>
        <div class="panel"><span class="tag">Fundação local</span>
        <h2>Seu estúdio está começando.</h2>
        <p>A navegação está disponível. Os fluxos de criação e publicação ainda não estão implementados.</p>
        <a class="button" href="/configuracoes">Configurar o espaço <span aria-hidden="true">↗</span></a></div>
        <div class="note"><h2>Estratégia · Criação · Cuidado</h2>
        <p>Antigo chique e novo moderno.<br>O universo da KIROS Aromas como ponto de partida.</p></div>'''
    elif section in ('marca', 'biblioteca'):
        from kiros.ui.library import render_library
        content = render_library(app, section, query or {})
    elif section == 'criar':
        from kiros.ui.creator import render_creator
        content = render_creator(app, query or {})
    elif section == 'conteudo':
        from kiros.ui.campaigns import render_campaigns_hub
        content = render_campaigns_hub(app, query or {})
    elif section == 'configuracoes':
        from kiros.ui.providers import render_providers_panel
        content = '<p class="eyebrow">Preferências locais e Provedores</p><h1>Configurações</h1>'
        if saved:
            content += '<p role="status" class="notice">Nome do espaço salvo neste dispositivo.</p>'
        content += f'''<div class="panel"><h2>Seu espaço</h2>
        <p>Este nome identifica o espaço local. A identidade oficial da marca é preservada.</p>
        <form method="post" action="/api/preferences">
        <label for="workspace">Nome do espaço</label>
        <input id="workspace" name="workspace_name" value="{name}" maxlength="80" required>
        <button type="submit">Salvar nome</button></form></div>
        <div class="note"><h2>Simulação local</h2>
        <p>Nenhuma IA externa está conectada. Geração e publicação reais exigem configuração explícita e autorização.</p></div>'''
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
    <div class="workspace"><header><span>{name}</span><span class="mode">Simulação local</span></header>
    <main id="main" tabindex="-1">{content}</main><footer>KIROS Aromas <span>Sorocaba · SP</span></footer></div></body></html>'''
