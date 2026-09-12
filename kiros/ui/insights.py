"""Insights estende o estúdio existente: Rubik/Inter, verde e papel, listas legíveis.

Operação local em três abas via GET. Fontes e limitações junto às observações,
formulários recolhidos e ações explícitas. Identidade e navegação preservadas.
"""
from html import escape
from kiros.insights import DIMENSIONS, VARIABLES, RISK_LABELS, STATES, TREND_FIELDS, TREND_LABELS, timestamp


def e(value):
    return escape(str(value), quote=True)


def date_label(value):
    return timestamp(value).strftime('%d/%m/%Y %H:%M UTC')


def field(name, label, value='', required=True, kind='text', multiline=False):
    attrs = f'id="{e(name)}" name="{e(name)}"' + (' required' if required else '')
    control = (f'<textarea {attrs} rows="3" maxlength="2000">{e(value)}</textarea>' if multiline else
               f'<input {attrs} type="{kind}" value="{e(value)}"' +
               (' min="0" max="1000000000" step="1"' if kind == 'number' else ' maxlength="2000"') + '>')
    return f'<label for="{e(name)}">{e(label)}</label>{control}'


def select(name, label, values):
    options = ''.join(f'<option value="{e(key)}">{e(value)}</option>' for key, value in values.items())
    return f'<label for="{name}">{label}</label><select id="{name}" name="{name}">{options}</select>'


def check(name, label):
    return f'<label class="check"><input type="checkbox" name="{name}" value="1">{label}</label>'


def form(action, contents, button):
    return f'<form method="post" action="/api/insights/{action}">{contents}<button type="submit">{button}</button></form>'


def render_insights(app, query):
    service = app.insights
    tab = query.get('tab', ['diversity'])[0]
    if tab not in ('diversity', 'sources', 'experiments'):
        tab = 'diversity'
    out = ['<div class="insights"><h1>Insights</h1><p class="intro">Variar com intenção. Experimentar com contexto.</p>']
    out.append('<p>Leitura local das fontes disponíveis. Nenhuma coleta externa ou publicação é iniciada aqui.</p>')
    if query.get('error'):
        out.append(f'<p role="alert" class="notice">{e(query["error"][0])}</p>')
    if query.get('saved'):
        out.append('<p role="status" class="notice">Registro salvo. Consulte a aba correspondente.</p>')
    out.append('<div class="insights-tabs" aria-label="Áreas de Insights">')
    for key, label in (('diversity', 'Diversidade'), ('sources', 'Fontes e tendências'), ('experiments', 'Experimentos A/B')):
        current = ' aria-current="page"' if key == tab else ''
        out.append(f'<a href="/insights?tab={key}"{current}>{label}</a>')
    out.append('</div>')
    if tab == 'diversity':
        out.append(render_diversity(service, query))
    elif tab == 'sources':
        out.append(render_sources(service, query))
    else:
        out.append(render_experiments(service))
    return ''.join(out) + '</div>'


def render_diversity(service, query):
    try:
        days = int(query.get('days', ['30'])[0])
        report = service.saturation(days)
    except ValueError:
        days, report = 30, service.saturation(30)
    out = ['<h2>Mapa de saturação</h2><form method="get" action="/insights" class="insights-filter">',
           '<input type="hidden" name="tab" value="diversity">',
           select('days', 'Janela de observação', {str(days): f'{days} dias', '7': '7 dias', '30': '30 dias', '90': '90 dias'}),
           '<button>Atualizar mapa</button></form>', f'<p class="hint">{e(report["basis"])}</p>']
    if report['map']:
        out.append('<div class="table-scroll" tabindex="0" role="region" aria-label="Mapa por dimensão"><table><caption>Ocorrências por dimensão e origem</caption>'
                   '<thead><tr><th>Dimensão / valor</th><th>Origem</th><th>Ocorrências</th><th>Frequência / 7 dias</th><th>Última ocorrência</th><th>Leitura</th></tr></thead><tbody>')
        for row in report['map']:
            out.append(f'<tr><td>{e(row["label"])}<br>{e(row["value"])}</td><td>{e(row["scope"])}</td>'
                       f'<td>{row["count"]} de {row["known"]} ({row["share"]}%)<br>{row["unknown"]} sem informação</td>'
                       f'<td>{row["per_week"]}</td><td>{date_label(row["last_seen"])}</td>'
                       f'<td>{"Repetição frequente — considerar variar" if row["warning"] else "Sem alerta nesta janela"}</td></tr>')
        out.append('</tbody></table></div>')
    else:
        out.append('<p class="notice">Ainda não há histórico nesta janela. Registre uma observação para começar o mapa.</p>')
    out.append('<p><strong>Dimensões sem dados:</strong> ' + e(', '.join(report['missing_dimensions']) or 'Nenhuma') + '.</p>')
    out.append('<details class="panel"><summary>Registrar conteúdo observado</summary><p>Descreva apenas atributos conhecidos. '
               'Campos vazios continuam desconhecidos. Uma repetição intencional pode ser registrada com seu motivo.</p>')
    contents = field('title', 'Conteúdo observado') + field('source', 'Origem / referência do conteúdo')
    contents += field('occurred_at', 'Data e horário com fuso', service.now().isoformat())
    contents += field('campaign_id', 'ID de campanha existente (opcional)', required=False)
    contents += '<div class="insights-fields">'
    for key, label in DIMENSIONS.items():
        if key != 'campaign':
            contents += '<div>' + field('dim_' + key, label, required=False) + '</div>'
    contents += '</div>' + field('intentional_reason', 'Motivo da repetição intencional (opcional)', required=False, multiline=True)
    out.append(form('observation', contents, 'Salvar observação') + '</details>')
    if report['samples']:
        out.append('<details class="panel"><summary>Consultar origem e intenção dos registros</summary><ul>')
        for sample in report['samples']:
            out.append(f'<li>{e(sample["title"])} — {e(sample["source"])} · {e(sample["time"].isoformat())}'
                       f'<p>{e(sample["intentional_reason"] or "Sem repetição intencional declarada.")}</p></li>')
        out.append('</ul></details>')
    return ''.join(out)


def render_sources(service, query):
    category, location, profile = [query.get(k, [''])[0] for k in ('category', 'location', 'profile')]
    include_mock = query.get('include_mock', [''])[0] == '1'
    rows = service.discover(category, location, profile, include_mock)
    out = ['<h2>Fontes e tendências</h2><p>Descubra perfis na base local por categoria, localização ou nome. '
           'As avaliações são informadas pelo operador, com fonte e data. Não há busca na internet nem inferência de acesso a perfis.</p>']
    filters = '<input type="hidden" name="tab" value="sources">'
    filters += field('category_filter', 'Categoria', category, False).replace('name="category_filter"', 'name="category"')
    filters += field('location_filter', 'Localização', location, False).replace('name="location_filter"', 'name="location"')
    filters += field('profile_filter', 'Perfil', profile, False).replace('name="profile_filter"', 'name="profile"')
    filters += check('include_mock', 'Incluir exemplos simulados').replace('value="1"', 'value="1"' + (' checked' if include_mock else ''))
    out.append('<form method="get" action="/insights">' + filters + '<button>Buscar na base local</button></form>')
    if not rows:
        out.append('<p class="notice">Nenhuma fonte corresponde à busca. Cadastre uma observação com referência verificável.</p>')
    for row in rows:
        out.append(f'<article class="insights-record"><h3>{e(row["profile"])}</h3>'
                   f'<p><strong>{"Simulação local — dados fictícios" if row["is_mock"] else "Observação informada — não verificada externamente"}</strong></p>'
                   f'<p>{e(row["category"])} · {e(row["location"])}</p><p>Fonte: {e(row["source"])}</p>'
                   f'<p>Observado em {date_label(row["observed_at"])}<br>Análise registrada em {date_label(row["recorded_at"])}</p>'
                   f'<p>{e(row["observation"])}</p><dl>')
        for key, label in zip(TREND_FIELDS, TREND_LABELS):
            out.append(f'<dt>{label}</dt><dd>{e(row["trend"][key])}</dd>')
        out.append('</dl><p class="hint">Use como referência para diferenciação. A fonte não concede direitos de reprodução.</p></article>')
    content = field('profile', 'Perfil / marca / referência') + field('category', 'Categoria') + field('location', 'Localização')
    content += field('source', 'Fonte: URL ou referência documental')
    content += field('observed_at', 'Data da observação com fuso', service.now().isoformat())
    content += field('observation', 'O que foi observado', multiline=True)
    content += check('is_mock', 'Este registro é simulado / fictício')
    for key, label in zip(TREND_FIELDS, TREND_LABELS):
        content += field(key, label + ' (avaliação do operador)', multiline=True)
    out.append('<details class="panel"><summary>Adicionar fonte e interpretação KIROS</summary>'
               + form('source', content, 'Salvar análise local') + '</details>')
    return ''.join(out)


def render_experiments(service):
    out = ['<h2>Experimentos A/B</h2><p>Compare uma variável por experimento. A aprovação cobre o acompanhamento local; '
           'geração e publicação continuam nos seus fluxos próprios.</p>']
    experiments = service.experiments()
    if not experiments:
        out.append('<p class="notice">Nenhum experimento criado. Comece por uma hipótese e uma métrica de eventos por observação.</p>')
    for item in experiments:
        eid = item['id']
        hidden = f'<input type="hidden" name="id" value="{eid}">'
        out.append(f'<article class="insights-record"><h3>{e(item["hypothesis"])}</h3>'
                   f'<p><strong>{STATES[item["state"]]}</strong> · Risco {RISK_LABELS[item["risk"]].lower()}</p>'
                   f'<p>{e(item["risk_reason"])}</p><dl><dt>Controle</dt><dd>{e(item["control"])}</dd>'
                   f'<dt>Variante</dt><dd>{e(item["variant"])}</dd><dt>Variável / métrica</dt>'
                   f'<dd>{VARIABLES[item["variable"]][0]} / {e(item["metric"])}</dd></dl>')
        if item['state'] == 'awaiting_approval':
            content = hidden + field('operator_' + eid, 'Responsável').replace(f'name="operator_{eid}"', 'name="operator"')
            content += field('authorization_' + eid, 'Escopo / referência da aprovação').replace(f'name="authorization_{eid}"', 'name="authorization"')
            content += check('confirmation', 'Aprovo explicitamente este experimento e seu risco')
            out.append(form('approve', content, 'Registrar aprovação'))
        elif item['state'] == 'approved':
            content = hidden + field('operator_' + eid, 'Responsável pelo acompanhamento').replace(f'name="operator_{eid}"', 'name="operator"')
            out.append(form('start', content, 'Iniciar acompanhamento local'))
        elif item['state'] == 'running':
            content = hidden
            for key, label in (('control_sample', 'Amostra do controle'), ('control_successes', 'Eventos no controle'),
                               ('variant_sample', 'Amostra da variante'), ('variant_successes', 'Eventos na variante')):
                content += field(key + '_' + eid, label, kind='number').replace(f'name="{key}_{eid}"', f'name="{key}"')
            content += field('source_' + eid, 'Fonte dos resultados').replace(f'name="source_{eid}"', 'name="source"')
            content += field('operator_' + eid, 'Responsável').replace(f'name="operator_{eid}"', 'name="operator"')
            out.append(form('result', content, 'Registrar resultado definitivo'))
        if item['result']:
            result = item['result']
            out.append(f'<p>Controle: {result["control_successes"]}/{result["control_sample"]} ({result["control_rate"]}%). '
                       f'Variante: {result["variant_successes"]}/{result["variant_sample"]} ({result["variant_rate"]}%).</p>'
                       f'<p><strong>Confiança {e(result["confidence"])}</strong>. {e(result["conclusion"])}</p>'
                       f'<p>Fonte: {e(result["source"])}</p><p class="hint">{e(result["basis"])}</p>')
        out.append('<details><summary>Histórico de autorização</summary><ul>')
        for event in item['events']:
            out.append(f'<li>{date_label(event["recorded_at"])} · {e(event["operator"])} · {e(event["action"])}</li>')
        out.append(f'</ul><p>{e(item["authorization"] or "Sem autorização registrada.")}</p></details></article>')
    content = field('hypothesis', 'Hipótese', multiline=True) + field('control', 'Controle', multiline=True)
    content += field('variant', 'Variante (mude apenas a variável escolhida)', multiline=True)
    content += select('variable', 'Variável', {key: f'{value[0]} — risco {RISK_LABELS[value[1]].lower()}' for key, value in VARIABLES.items()})
    content += field('metric', 'Métrica binária (ex.: visitas que geraram clique)')
    content += check('protected_change', 'Envolve identidade, direitos de uso ou dados comerciais (risco alto)')
    content += field('authorization', 'Autorização já existente (opcional, válida automaticamente só para risco baixo)', required=False)
    content += field('operator', 'Responsável por essa autorização (se informada)', required=False)
    out.append('<details class="panel"><summary>Criar experimento</summary>' + form('experiment', content, 'Criar experimento') + '</details>')
    return ''.join(out)


def dispatch_insights(service, action, data):
    get = lambda key: data.get(key, '')
    if action == 'observation':
        dims = {key: get('dim_' + key) for key in DIMENSIONS if get('dim_' + key).strip()}
        return service.record_diversity(get('title'), dims, get('occurred_at'), get('source'),
                                        get('campaign_id') or None, get('intentional_reason'))
    if action == 'source':
        return service.record_competitor(get('profile'), get('category'), get('location'), get('source'),
                                         get('observed_at'), get('observation'),
                                         {key: get(key) for key in TREND_FIELDS}, get('is_mock') == '1')
    if action == 'experiment':
        return service.create_experiment(get('hypothesis'), get('control'), get('variant'), get('variable'),
                                         get('metric'), get('protected_change') == '1', get('authorization'), get('operator'))
    if action == 'approve':
        return service.approve_experiment(get('id'), get('operator'), get('confirmation') == '1', get('authorization'))
    if action == 'start':
        return service.start_experiment(get('id'), get('operator'))
    if action == 'result':
        keys = ('control_sample', 'control_successes', 'variant_sample', 'variant_successes')
        try:
            numbers = [int(get(key)) for key in keys]
        except ValueError:
            raise ValueError('Preencha amostras e eventos com números inteiros.') from None
        return service.record_result(get('id'), *numbers, get('source'), get('operator'))
    raise ValueError('Operação de Insights não encontrada.')
