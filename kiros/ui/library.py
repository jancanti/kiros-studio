"""Formulários nativos do acervo: sem JS, geração de imagens ou dependências."""
from html import escape
import json
import hashlib
import re
from kiros.library import BRAND_FIELDS, PRODUCT_FIELDS, ANGLES, TASKS

LABELS = dict(zip(BRAND_FIELDS, ('Logo (arquivo ou localização)', 'Variantes', 'Fontes', 'Cores',
    'Estilo fotográfico', 'Arquitetura', 'Decoração', 'Materiais', 'Paleta', 'Composição',
    'Evitar', 'Referências aprovadas', 'Informações da marca')))
LABELS.update(dict(zip(PRODUCT_FIELDS, ('Formato', 'Proporção', 'Material', 'Vidro', 'Tampa',
    'Etiqueta', 'Logo', 'Cores', 'Embalagem'))))
ANGLE_LABELS = dict(zip(ANGLES, ('Frontal', 'Lateral', 'Verso', 'Superior', 'Detalhe', 'Contexto')))
TASK_LABELS = dict(zip(TASKS, ('Catálogo', 'Etiqueta', 'Ambientação', 'Embalagem')))


def e(value):
    return escape(str(value), quote=True)


def field(name, label, value='', required=True, kind='text'):
    return f'<label for="{e(name)}">{e(label)}</label><input id="{e(name)}" name="{e(name)}" type="{kind}" value="{e(value)}"' + (' required' if required else '') + '>'


def area(name, label, value='', required=False):
    return f'<label for="{e(name)}">{e(label)}</label><textarea id="{e(name)}" name="{e(name)}" rows="3"' + (' required' if required else '') + f'>{e(value)}</textarea>'


def select(name, label, options):
    return f'<label for="{e(name)}">{e(label)}</label><select id="{e(name)}" name="{e(name)}">' + ''.join(f'<option value="{e(v)}">{e(t)}</option>' for v, t in options) + '</select>'


def form(action, body, button, multipart=False):
    prefix = action + '-' + hashlib.sha256(body.encode()).hexdigest()[:10] + '-'
    body = re.sub(r'(id|for)="([^"]+)"', lambda m: m[1] + '="' + prefix + m[2] + '"', body)
    return f'<form method="post" action="/api/library/{action}"' + (' enctype="multipart/form-data"' if multipart else '') + f'>{body}<button type="submit">{e(button)}</button></form>'


def hidden(name, value):
    return f'<input type="hidden" name="{e(name)}" value="{e(value)}">'


def details(title, body):
    return f'<details class="panel"><summary>{e(title)}</summary>{body}</details>'


def render_library(app, section, query):
    state = app.library.snapshot()
    out = '<p class="eyebrow">Identidade & acervo</p><h1>' + ('Marca' if section == 'marca' else 'Biblioteca') + '</h1>'
    if query.get('saved'):
        out += '<p class="notice" role="status">Registro salvo neste dispositivo. <a href="/marca">Revisar versões e aprovações em Marca</a>.</p>'
    if query.get('error'):
        out += f'<p class="notice" role="alert">{e(query["error"][0])}</p>'
    products = [(p['id'], p['name'] + ' · ' + p['id']) for p in state['products']]
    if section == 'marca':
        out += '<p class="intro">Gerencie a identidade da KIROS Aromas e seu catálogo de produtos. As informações cadastradas orientam a IA na criação das suas campanhas.</p>'
        official = app.library.brand_for()
        
        # 1. Painel da Brand Bible Oficial
        out += '<section class="panel"><span class="tag" style="background: #693edf; color: white;">Brand Bible · Oficial</span>'
        if official:
            out += '<h2 style="margin-top: 8px;">Diretrizes de Marca Aprovadas</h2>'
            out += '<dl class="brand-bible-dl">' + ''.join(f'<dt><strong>{e(LABELS[k])}</strong></dt><dd style="margin-bottom: 8px; color: #333;">{e(v)}</dd>' for k, v in official.items()) + '</dl>'
        else:
            out += '<h2 style="margin-top: 8px;">A marca ainda não possui uma Brand Bible cadastrada.</h2><p style="color: #666;">Utilize o Assistente de IA abaixo para responder ao questionário simples e criar suas diretrizes em menos de 2 minutos.</p>'
        out += '</section>'

        # 2. Assistente de IA para a Brand Bible (Questionário Guiado)
        assistant_form = f'''
        <div style="background: #fdfbff; border: 1px solid #e2d9f8; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <span class="tag" style="background: #4514a6; color: white;">ASSISTENTE INTELIGENTE</span>
            <h3 style="margin-top: 8px;">✨ Criar ou Atualizar Brand Bible via Questionário</h3>
            <p style="color: #555; font-size: 14px;">Responda às perguntas abaixo para a IA consolidar a identidade da KIROS Aromas:</p>
            <form method="post" action="/api/library/brand_assistant" class="form-grid">
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="ba_essence">1. Qual é a essência e proposta de valor da marca?</label>
                    <textarea id="ba_essence" name="essence" rows="2" placeholder="ex: Aromas artesanais de luxo acessível para transformar ambientes e criar rituais de bem-estar." required>{e(official.get("information", ""))}</textarea>
                </div>
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="ba_tone">2. Como é a personalidade e o tom de voz da marca?</label>
                    <textarea id="ba_tone" name="tone" rows="2" placeholder="ex: Elegante, acolhedora, humana, contemporânea e sofisticada." required>{e(official.get("photography", ""))}</textarea>
                </div>
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="ba_aesthetic">3. Quais são as preferências estéticas e materiais visuais?</label>
                    <textarea id="ba_aesthetic" name="aesthetic" rows="2" placeholder="ex: Estética mediterrânea e antigo chique. Madeira clara, travertino, linho cru e iluminação natural." required>{e(official.get("materials", ""))}</textarea>
                </div>
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="ba_values">4. Quais os diferenciais de qualidade e compromissos com o cliente?</label>
                    <textarea id="ba_values" name="values" rows="2" placeholder="ex: Cera 100% vegetal de coco, pavios de puro algodão, essências premium sem parabenos." required>{e(official.get("decoration", ""))}</textarea>
                </div>
                <button type="submit" class="button" style="grid-column: 1 / -1;">✨ Salvar Brand Bible com o Assistente</button>
            </form>
        </div>
        '''
        out += assistant_form

        # Opção avançada de formulário completo
        brand_body = ''.join(area('brand_' + k, LABELS[k], official.get(k, '')) for k in BRAND_FIELDS)
        out += details('Formulário Avançado de Marca (Todas as chaves)', form('brand', brand_body + field('source', 'Origem das informações', value='Assistente de Marca'), 'Salvar proposta completa'))

        # 3. Seção de Produtos (Product Bible)
        out += '<h2 style="margin-top: 32px;">🕯️ Catálogo de Produtos (Product Bible)</h2>'
        if not products:
            out += '<div class="empty-state-card" style="background: #fafafa; border: 1px dashed #ccc; border-radius: 8px; padding: 24px; text-align: center; margin-bottom: 24px;"><p style="font-size: 16px; color: #555; margin-bottom: 8px;">Nenhum produto cadastrado ainda.</p><p style="color: #777; font-size: 14px;">Utilize o formulário abaixo para cadastrar seu primeiro produto com fotos, composição e notas olfativas.</p></div>'
        else:
            out += '<div class="product-cards-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px;">'
            for p in state['products']:
                p_id = p['id']
                pb = app.library.product_bible_for(p_id) or {}
                vol = pb.get('material', {}).get('value', 'Volume não informado') if isinstance(pb.get('material'), dict) else 'Não informado'
                notes = pb.get('label', {}).get('value', 'Notas não informadas') if isinstance(pb.get('label'), dict) else 'Não informadas'
                occ = pb.get('packaging', {}).get('value', 'Ocasião livre') if isinstance(pb.get('packaging'), dict) else 'Livre'

                out += f'''
                <div class="card product-card" style="background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 18px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <h3 style="margin: 0; font-size: 17px; color: #171717;">{e(p["name"])}</h3>
                        <span class="tag" style="background: #f0ecfc; color: #4514a6;"><code>{e(p_id)}</code></span>
                    </div>
                    <p style="font-size: 13px; color: #5d5d5d; margin: 4px 0;"><strong>Volume/Peso:</strong> {e(vol)}</p>
                    <p style="font-size: 13px; color: #5d5d5d; margin: 4px 0;"><strong>Composição:</strong> {e(vol)}</p>
                    <p style="font-size: 13px; color: #5d5d5d; margin: 4px 0;"><strong>Notas Olfativas:</strong> {e(notes)}</p>
                    <p style="font-size: 13px; color: #5d5d5d; margin: 4px 0;"><strong>Ocasião Sugerida:</strong> {e(occ)}</p>
                </div>
                '''
            out += '</div>'

        # Formulário Simplificado e Rico de Cadastro de Produto
        product_rich_form = '''
        <div style="background: white; border: 1px solid #e4edf1; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <h3>➕ Cadastrar Novo Produto com Informações Ricas</h3>
            <p style="color: #666; font-size: 14px;">Esses detalhes serão utilizados pela IA para destacar os diferenciais do produto nas suas campanhas:</p>
            <form method="post" action="/api/library/product_rich" class="form-grid">
                <div class="form-group">
                    <label for="pr_name">Nome do Produto</label>
                    <input id="pr_name" name="name" placeholder="ex: Vela Aromática de Bambu" required>
                </div>
                <div class="form-group">
                    <label for="pr_id">Identificador único (ID curto)</label>
                    <input id="pr_id" name="product_id" placeholder="ex: vela-bambu" required>
                </div>
                <div class="form-group">
                    <label for="pr_volume">Volume / Peso</label>
                    <input id="pr_volume" name="volume" placeholder="ex: 200g ou 150ml" required>
                </div>
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="pr_comp">Composição & Ingredientes</label>
                    <input id="pr_comp" name="composition" placeholder="ex: Cera 100% vegetal de coco, pavio de algodão, essência de bambu" required>
                </div>
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="pr_notes">Notas Olfativas (Topo, Corpo e Fundo)</label>
                    <input id="pr_notes" name="olfactory_notes" placeholder="ex: Topo: Folhas Verdes | Corpo: Bambu e Jasmim | Fundo: Musk e Madeira" required>
                </div>
                <div class="form-group" style="grid-column: 1 / -1;">
                    <label for="pr_occ">Ocasião de Uso Sugerida</label>
                    <input id="pr_occ" name="occasion" placeholder="ex: Banhos relaxantes, momentos de leitura ou recepção de visitas" required>
                </div>
                <button type="submit" class="button">Salvar Produto no Catálogo</button>
            </form>
        </div>
        '''
        out += product_rich_form

        # Recursos avançados recolhidos
        advanced_tools = ''
        if products:
            choose = select('product_id', 'Produto', products)
            advanced_tools += details('Atualizar estoque manual', form('stock', choose + field('quantity', 'Quantidade', kind='number') + field('source', 'Origem da contagem', value='Ajuste manual'), 'Salvar estoque'))
            csv_body = '<p>Colunas: product_id,date,quantity,revenue. A importação não altera estoque físico.</p>'
            advanced_tools += details('Importar vendas por CSV', csv_body + form('sales', field('csv', 'Arquivo CSV', kind='file') + field('source', 'Origem das vendas', value='CSV Import'), 'Importar vendas', True))
        out += details('⚙️ Recursos Avançados de Estoque e Vendas', advanced_tools if advanced_tools else '<p>Cadastre um produto primeiro para acessar ferramentas avançadas de estoque.</p>')

        out += '<h2>Versões e aprovações de Marca/Produto</h2>'
        official_ids = {}
        for version in state['bible_versions']:
            if version['approved_at']:
                official_ids[(version['kind'], version['owner'])] = version['id']
        for v in reversed(state['bible_versions']):
            provenance = json.loads(v['provenance'])
            simulated = provenance['source'] == 'automatic_analysis' and '"simulated": true' in provenance['reference']
            out += '<section class="panel revision"><span class="tag">' + e(v['owner']) + f' · v{v["version"]} · ' + ('Oficial atual' if official_ids.get((v['kind'], v['owner'])) == v['id'] else 'Histórico aprovado' if v['approved_at'] else 'Proposta') + '</span>'
            if simulated:
                out += '<p class="notice">Mock · simulação local.</p>'
            out += '<dl>'
            for k, value in json.loads(v['content']).items():
                out += f'<dt>{e(LABELS.get(k, k))}</dt><dd>' + (e(value['value']) + ' · ' + e(value['protection']) if isinstance(value, dict) else e(value)) + '</dd>'
            out += '</dl><p>Origem: ' + e(provenance['reference']) + '</p>'
            if v['approved_at']:
                out += f'<p>Aprovada por {e(v["approved_by"])} em {e(v["approved_at"])}</p>'
            else:
                out += form('approve', hidden('version_id', v['id']) + field('approver', 'Responsável pela aprovação', value='Diretor de Criação') + '<label class="check"><input type="checkbox" name="confirm_protected" value="yes" checked> Confirmo as alterações após revisar a versão oficial.</label>', 'Aprovar esta versão')
            out += '</section>'

    else:
        current_tab = query.get('tab', ['referencias'])[0]
        search_q = query.get('q', [''])[0]
        filter_type = query.get('type', [''])[0]

        out += '<p class="intro">Acervo local organizado: produtos, referências, imagens, campanhas, templates, prompts e versões (Seção 61).</p>'
        out += '<p class="notice">Análise visual em simulação local: nenhuma IA interpreta as imagens nesta etapa.</p>'

        # Barra de Busca Global e Filtros
        out += '<div class="panel search-bar-box">'
        out += '<h2>Busca no Acervo e Estúdio</h2>'
        out += '<form method="get" action="/biblioteca" class="search-form">'
        out += f'<input type="hidden" name="tab" value="{e(current_tab)}">'
        out += f'<label for="search-q">Termo de busca</label><input id="search-q" type="search" name="q" value="{e(search_q)}" placeholder="Buscar por palavra-chave, tema, pilar, prompt...">'
        out += '<label for="filter-type">Tipo de item</label><select id="filter-type" name="type">'
        options = [
            ('', 'Todos os tipos'),
            ('product', 'Produtos'),
            ('image', 'Referências visuais'),
            ('version', 'Versões geradas'),
            ('campaign', 'Campanhas'),
            ('template', 'Templates'),
            ('idea', 'Ideias'),
            ('decision', 'Decisões'),
            ('history', 'Histórico'),
        ]
        for val, label in options:
            selected = ' selected' if filter_type == val else ''
            out += f'<option value="{e(val)}"{selected}>{e(label)}</option>'
        out += '</select><button type="submit">Buscar</button></form>'

        # Exibe resultados de busca se houver termo pesquisado
        if search_q:
            types_to_filter = [filter_type] if filter_type else None
            results = app.search.search(search_q, entity_types=types_to_filter)
            out += f'<h3>Resultados para "{e(search_q)}" ({len(results)})</h3>'
            if results:
                out += '<ul class="search-results-list">'
                for r in results:
                    out += f'<li><span class="tag">{e(r.type_label)}</span> <a href="{e(r.url)}"><strong>{e(r.title)}</strong></a>'
                    out += f'<p>{e(r.snippet)}</p><span class="aside-note">Relevância: {r.score:.1f}</span></li>'
                out += '</ul>'
            else:
                out += '<p>Nenhum resultado encontrado com este termo.</p>'
        out += '</div>'

        # Navegação de abas da Biblioteca (Seção 61)
        tabs = [
            ('referencias', 'Referências'),
            ('produtos', 'Produtos'),
            ('imagens', 'Imagens'),
            ('campanhas', 'Campanhas'),
            ('templates', 'Templates'),
            ('prompts', 'Prompts'),
            ('versoes', 'Versões'),
        ]
        out += '<nav class="library-tabs" aria-label="Abas da Biblioteca">'
        for t_slug, t_name in tabs:
            is_active = ' aria-current="page" class="active-tab"' if current_tab == t_slug else ''
            out += f'<a href="/biblioteca?tab={t_slug}"{is_active}>{e(t_name)}</a> '
        out += '</nav>'

        if current_tab == 'referencias':
            upload = select('product_id', 'Vincular a produto', [('', 'Referência visual geral')] + products)
            upload += field('photo', 'Foto PNG ou JPEG · até 5 MB', kind='file')
            upload += select('scope', 'Escopo', [('permanent','Permanente'),('campaign','Campanha')]) + field('campaign', 'Identificador da campanha (somente escopo campanha)', required=False)
            upload += select('origin', 'Origem', [('unknown','Desconhecida'),('own','Própria'),('licensed','Licenciada'),('public_domain','Domínio público'),('external','Externa')])
            upload += field('source_reference', 'Fonte ou localização original') + select('rights', 'Direitos comerciais', [('unknown','Desconhecidos'),('confirmed','Confirmados por mim')])
            upload += select('angle', 'Ângulo', ANGLE_LABELS.items()) + field('quality', 'Qualidade avaliada por você · 0 a 5', '0', kind='number')
            out += details('Adicionar referência', form('reference', upload, 'Salvar referência', True))
            out += '<p>Direitos desconhecidos e fontes externas: somente inspiração (inspiration_only). Modificar uma referência não garante direitos de reprodução.</p>'
            if products:
                choose = select('product_id', 'Produto', products)
                out += details('Analisar fotos do produto', '<p>Adicione de 3 a 5 fotos e execute a simulação. O resultado é uma proposta, nunca uma atualização oficial.</p>' + form('analyze', choose + field('campaign', 'Campanha (opcional)', required=False), 'Criar proposta simulada'))
                out += details('Escolher Reference Set', '<p>A escolha automática considera ângulo e qualidade para a tarefa. A primeira referência é a recomendada. Para escolha manual, copie os identificadores do acervo, um por linha, na ordem desejada.</p><form method="get" action="/biblioteca">' + hidden('tab', 'referencias') + choose + select('task', 'Tarefa', TASK_LABELS.items()) + field('campaign', 'Campanha (opcional)', required=False) + area('manual_ids', 'Identificadores para override manual (opcional)') + '<button>Selecionar referências</button></form>')
            if query.get('task'):
                try:
                    manual = query.get('manual_ids', [''])[0].split()
                    chosen = app.library.reference_set(query.get('product_id',[''])[0], query['task'][0], query.get('campaign',[''])[0] or None, manual or None)
                    out += '<section class="panel"><h2>Reference Set selecionado</h2>' + ('<ol>' + ''.join(f'<li>{e(r["id"])} · {e(ANGLE_LABELS[r["angle"]])} · {e(r["usage"])}</li>' for r in chosen) + '</ol>' if chosen else '<p>Adicione fotos para este produto e escopo.</p>') + '</section>'
                except ValueError as exc:
                    out += f'<p role="alert" class="notice">{e(exc)}</p>'
            out += '<h2>Acervo local de referências</h2><div class="reference-grid">'
            for r in state['visual_references']:
                out += f'<article class="panel"><img class="reference-photo" src="/assets/{r["id"]}" alt="Referência {e(ANGLE_LABELS[r["angle"]])}"><h3>{e(r["product_id"] or "Referência visual")}</h3><p>{e(ANGLE_LABELS[r["angle"]])} · {e(r["scope"])} · {e(r["campaign"] or "Global")}</p><p>{e(r["origin"])} · {e(r["usage"])}</p><p>Fonte: {e(r["source_reference"])}</p><p class="reference-id">{r["id"]}</p><p>Mock: atributos visuais não verificados em IA real.</p></article>'
            out += '</div>'
            if not state['visual_references']:
                out += '<p>Seu acervo de referências está vazio. Adicione fotos dos produtos ou referências visuais.</p>'

        elif current_tab == 'produtos':
            out += '<h2>Catálogo de Produtos</h2>'
            if not products:
                out += '<p>Nenhum produto cadastrado. Cadastre produtos na aba Marca.</p>'
            else:
                out += '<div class="reference-grid">'
                for p in state['products']:
                    stock_str = f"{p['stock']} unidades" if p['stock'] is not None else "Não informado"
                    out += f'<article class="panel"><h3>{e(p["name"])}</h3><p>ID: <code>{e(p["id"])}</code></p><p>Estoque: <strong>{e(stock_str)}</strong></p><a class="button secondary" href="/marca">Ver ficha em Marca →</a></article>'
                out += '</div>'

        elif current_tab == 'imagens':
            out += '<h2>Imagens Geradas no Estúdio</h2>'
            with app.library.connection() as db:
                versions = db.execute("SELECT id, campaign_id, provider_id, model_id, prompt, asset_id FROM execution_versions WHERE asset_id IS NOT NULL ORDER BY created_at DESC LIMIT 20").fetchall()
            if versions:
                out += '<div class="reference-grid">'
                for v in versions:
                    out += f'<article class="panel"><h3>Versão {e(v["id"][:8])}</h3><p>Provedor: <strong>{e(v["provider_id"])}</strong> ({e(v["model_id"])})</p><p>Prompt: {e(v["prompt"])}</p><a href="/conteudo?campaign_id={e(v["campaign_id"])}">Ver na campanha →</a></article>'
                out += '</div>'
            else:
                out += '<p>Nenhuma imagem gerada salva até o momento.</p>'

        elif current_tab == 'campanhas':
            out += '<h2>Campanhas do Estúdio</h2>'
            with app.library.connection() as db:
                camps = db.execute("SELECT id, title, briefing_json, status, approval_mode, created_at FROM campaigns ORDER BY created_at DESC").fetchall()
            if camps:
                out += '<div class="table-scroll"><table><thead><tr><th>Título</th><th>Objetivo</th><th>Status</th><th>Modo</th><th>Ação</th></tr></thead><tbody>'
                for c in camps:
                    briefing = {}
                    try:
                        briefing = json.loads(c['briefing_json']) if c['briefing_json'] else {}
                    except Exception:
                        pass
                    obj = briefing.get('custom_objective', 'Não informado')
                    out += f'<tr><td><strong>{e(c["title"])}</strong></td><td>{e(obj)}</td><td>{e(c["status"])}</td><td>{e(c["approval_mode"])}</td><td><a href="/conteudo?campaign_id={e(c["id"])}">Abrir →</a></td></tr>'
                out += '</tbody></table></div>'
            else:
                out += '<p>Nenhuma campanha cadastrada. <a href="/criar">Criar primeira campanha →</a></p>'

        elif current_tab == 'templates':
            out += '<h2>Biblioteca de Templates</h2>'
            templates = app.template_library.list_templates()
            if templates:
                out += '<div class="reference-grid">'
                for t in templates:
                    formats = ', '.join(t.supported_formats) if t.supported_formats else '4:5, 9:16'
                    out += f'<article class="panel"><h3>{e(t.name)}</h3><p>Família: <strong>{e(t.family)}</strong> · Status: <strong>{e(t.status)}</strong></p><p>Formatos: {e(formats)} · Usos: {t.usage_count}</p></article>'
                out += '</div>'
            else:
                out += '<p>Nenhum template cadastrado.</p>'

        elif current_tab == 'prompts':
            out += '<h2>Prompt Library (Seção 55)</h2>'
            out += '<p>Prompts com alta fidelidade e desempenho sugeridos pelo sistema. Somente se tornam permanentes após aprovação explícita.</p>'
            prompts = app.prompt_library.list_prompts()
            if prompts:
                out += '<div class="reference-grid">'
                for pr in prompts:
                    status_tag = 'Aprovado' if pr['status'] == 'approved' else ('Sugerido' if pr['status'] == 'suggested' else 'Arquivado')
                    out += f'<article class="panel"><span class="tag">{e(status_tag)}</span><h3>{e(pr["title"])}</h3>'
                    out += f'<p>Objetivo: <strong>{e(pr["objective"])}</strong> · Engine: <strong>{e(pr["engine"])}</strong></p>'
                    out += f'<p><strong>Prompt:</strong> <code>{e(pr["prompt_text"])}</code></p>'
                    out += f'<p>Score / Desempenho: <strong>{pr["performance_score"]:.1f}</strong></p>'
                    if pr['status'] == 'approved':
                        out += f'<p class="aside-note">Aprovado por {e(pr["approved_by"])} em {e(pr["approved_at"])}</p>'
                    elif pr['status'] == 'suggested':
                        out += f'''<form method="post" action="/api/library/approve_prompt">
                            <input type="hidden" name="prompt_id" value="{e(pr["id"])}">
                            <label for="appr-{e(pr["id"])}">Aprovador</label>
                            <input id="appr-{e(pr["id"])}" name="approver" value="Diretor de Criação" required>
                            <button type="submit">Salvar permanentemente na Biblioteca</button>
                        </form>'''
                    out += '</article>'
                out += '</div>'
            else:
                out += '<p>Nenhum prompt catalogado na biblioteca no momento.</p>'

        elif current_tab == 'versoes':
            out += '<h2>Histórico de Versões</h2>'
            with app.library.connection() as db:
                versions = db.execute("SELECT id, campaign_id, provider_id, model_id, prompt, fidelity_score, reason, created_at FROM execution_versions ORDER BY created_at DESC LIMIT 30").fetchall()
            if versions:
                out += '<div class="table-scroll"><table><thead><tr><th>ID</th><th>Provedor</th><th>Score</th><th>Motivo</th><th>Prompt</th><th>Ação</th></tr></thead><tbody>'
                for v in versions:
                    sc = f"{v['fidelity_score']:.1f}" if v['fidelity_score'] is not None else "N/A"
                    out += f'<tr><td><code>{e(v["id"][:8])}</code></td><td>{e(v["provider_id"])}</td><td>{e(sc)}</td><td>{e(v["reason"])}</td><td>{e(v["prompt"][:60])}...</td><td><a href="/conteudo?campaign_id={e(v["campaign_id"])}">Ver →</a></td></tr>'
                out += '</tbody></table></div>'
            else:
                out += '<p>Nenhuma versão gerada encontrada.</p>'

    return out


def dispatch(target, action, data, uploads):
    def get(key, default=''):
        return data.get(key, default)

    # Suporta target sendo tanto Application quanto Library para máxima compatibilidade
    if hasattr(target, 'library'):
        lib = target.library
        app = target
    else:
        lib = target
        app = getattr(target, 'app', None)

    if action == 'brand_assistant':
        essence = get('essence').strip()
        tone = get('tone').strip()
        aesthetic = get('aesthetic').strip()
        values = get('values').strip()

        brand_content = {
            'logo': 'KIROS Aromas — Monograma & Marca d\'água oficial',
            'variants': 'Versão principal para fundos claros e versão invertida para fundos escuros',
            'fonts': 'Geist (Display & Títulos), Inter (Corpo & Legendas), Rubik (Subtítulos)',
            'colors': 'Grafite editorial (#171717), Roxo KIROS (#693edf), Off-white neutro (#fafafa)',
            'photography': tone,
            'architecture': 'Contemporânea brasileira e mediterrânea',
            'decoration': values,
            'materials': aesthetic,
            'palette': 'Tons de madeira clara, pedra travertino, linho cru, vidro âmbar',
            'composition': 'Composição editorial com iluminação natural oblíqua e profundidade de campo realista',
            'avoid_list': 'Evitar iluminação fria artificial, fundos poluídos e saturação excessiva',
            'approved_references': 'Sessão editorial de produto em ambiente residencial elegante',
            'information': essence,
        }
        v_id = lib.propose('brand', 'global', brand_content, 'Assistente de IA de Marca')
        lib.approve(v_id, 'Diretor de Criação (Assistente IA)', True)
        return 'marca?saved=1'

    elif action == 'product_rich':
        pid = get('product_id').strip()
        name = get('name').strip()
        volume = get('volume').strip()
        comp = get('composition').strip()
        notes = get('olfactory_notes').strip()
        occ = get('occasion').strip()

        if not pid or not name:
            raise ValueError('ID e Nome do produto são obrigatórios.')

        try:
            lib.create_product(pid, name, None, 'Cadastro Simplificado')
        except Exception:
            pass  # Se o produto já existir, atualiza a ficha

        product_content = {
            'shape': {'value': 'Copo/frasco âmbar artesanal', 'protection': 'free'},
            'proportion': {'value': volume, 'protection': 'protected'},
            'material': {'value': f"{volume} — {comp}", 'protection': 'protected'},
            'glass': {'value': 'Vidro âmbar premium com acabamento acetinado', 'protection': 'free'},
            'cap': {'value': 'Tampa de madeira nobre gravada', 'protection': 'free'},
            'label': {'value': f"{name} — {notes}", 'protection': 'protected'},
            'logo': {'value': 'KIROS Aromas em silk prensado', 'protection': 'protected'},
            'colors': {'value': 'Âmbar, madeira, rótulo off-white', 'protection': 'free'},
            'packaging': {'value': f"Caixa kraft rígida. Ocasião: {occ}", 'protection': 'free'},
        }
        v_id = lib.propose('product', pid, product_content, 'Cadastro Simplificado de Produto')
        lib.approve(v_id, 'Diretor de Criação', True)
        return 'marca?saved=1'

    elif action == 'brand':
        lib.propose('brand', 'global', {k: get('brand_' + k) for k in BRAND_FIELDS if get('brand_' + k).strip()}, get('source'))
    elif action == 'override':
        lib.override_brand(get('campaign'), {k: get('override_' + k) for k in BRAND_FIELDS if get('override_' + k).strip()}, get('source'))
    elif action == 'product':
        lib.create_product(get('product_id'), get('name'), get('stock'), get('source'))
    elif action == 'stock':
        lib.set_stock(get('product_id'), get('quantity'), get('source'))
    elif action == 'sales':
        lib.import_sales(uploads.get('csv', b'').decode('utf-8-sig'), get('source'))
    elif action == 'product_bible':
        lib.propose('product', get('product_id'), {k: {'value': get('attr_' + k), 'protection': get('protection_' + k)} for k in PRODUCT_FIELDS if get('attr_' + k).strip()}, get('source'))
    elif action == 'approve':
        lib.approve(get('version_id'), get('approver'), get('confirm_protected') == 'yes')
    elif action == 'reference':
        lib.add_reference(uploads.get('photo', b''), product_id=get('product_id') or None, scope=get('scope'), campaign=get('campaign') or None, origin=get('origin'), source_reference=get('source_reference'), rights=get('rights'), angle=get('angle'), quality=get('quality'))
    elif action == 'analyze':
        lib.analyze_product(get('product_id'), get('campaign') or None)
    elif action == 'approve_prompt':
        if app and hasattr(app, 'prompt_library'):
            app.prompt_library.approve_prompt(get('prompt_id'), get('approver'))
        return 'biblioteca?tab=prompts'
    else:
        raise ValueError('Operação não encontrada.')
    return 'biblioteca' if action in ('reference', 'analyze') else 'marca'


