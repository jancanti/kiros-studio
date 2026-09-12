"""Interface visual do Dashboard Contextual (Seção 59).

Renderiza os 6 blocos obrigatórios da especificação:
- Hoje
- Oportunidade
- Próximo passo recomendado
- Calendário
- Criação
- Aprendizados
"""
from html import escape
from typing import Any, Dict


def e(val: Any) -> str:
    return escape(str(val if val is not None else ''), quote=True)


def render_dashboard(app, query: Dict[str, Any]) -> str:
    data = app.dashboard.get_dashboard_data()
    hoje = data['hoje']
    oportunidade = data['oportunidade']
    proximo_passo = data['proximo_passo']
    calendario = data['calendario']
    criacao = data['criacao']
    aprendizados = data['aprendizados']

    out = '<p class="eyebrow">Visão geral do estúdio</p>'
    out += '<h1>Dashboard Contextual</h1>'
    out += '<p class="intro">Intenção antes da criação. Seus dados operacionais e estratégicos integrados em um só lugar.</p>'

    if query.get('notice'):
        out += f'<p class="notice" role="status">{e(query["notice"][0])}</p>'
    if query.get('error'):
        out += f'<p class="notice" role="alert">{e(query["error"][0])}</p>'

    # Grid de 2 colunas com os blocos
    out += '<div class="dashboard-grid">'

    # 1. Bloco: Hoje
    out += '<section class="panel dashboard-card">'
    out += '<span class="tag">Hoje</span>'
    out += f'<h2>{e(hoje["data_formatada"])}</h2>'
    out += f'<p><strong>Fila de geração:</strong> {e(hoje["queue_status"])}</p>'
    out += f'<p>Tarefas pendentes: <strong>{hoje["pending_jobs"]}</strong> · Concluídas: <strong>{hoje["completed_jobs"]}</strong></p>'
    out += f'<p class="aside-note">Ambiente: {e(hoje["mode"])}</p>'
    if hoje['queue_paused']:
        out += '<form method="post" action="/api/command"><input type="hidden" name="command" value="Retome a geração"><button type="submit">Retomar fila</button></form>'
    else:
        out += '<form method="post" action="/api/command"><input type="hidden" name="command" value="Pause a geração"><button type="submit" class="secondary">Pausar fila</button></form>'
    out += '</section>'

    # 2. Bloco: Oportunidade
    out += '<section class="panel dashboard-card">'
    out += '<span class="tag">Oportunidade</span>'
    out += f'<h2>{e(oportunidade["title"])}</h2>'
    out += f'<p>{e(oportunidade["description"])}</p>'
    out += f'<p>Pilar recomendado: <strong>{e(oportunidade["recommended_pillar"])}</strong></p>'
    out += f'<a class="button" href="{e(oportunidade.get("target_url", "/criar"))}">Explorar oportunidade <span aria-hidden="true">→</span></a>'
    out += '</section>'

    # 3. Bloco: Próximo passo recomendado
    out += '<section class="panel dashboard-card highlight-step">'
    out += f'<span class="tag priority-{e(proximo_passo["priority"])}">Próximo passo recomendado</span>'
    out += f'<h2>{e(proximo_passo["action_label"])}</h2>'
    out += f'<p>{e(proximo_passo["description"])}</p>'
    out += f'<a class="button" href="{e(proximo_passo["url"])}">Executar ação recomendada <span aria-hidden="true">→</span></a>'
    out += '</section>'

    # 4. Bloco: Calendário
    out += '<section class="panel dashboard-card">'
    out += '<span class="tag">Calendário</span>'
    out += f'<h2>Postagens agendadas: {calendario["scheduled_count"]}</h2>'
    if calendario['upcoming_posts']:
        out += '<ul class="dashboard-list">'
        for post in calendario['upcoming_posts']:
            out += f'<li><strong>{e(post["title"])}</strong> ({e(post["pillar"])}) — {e(post["publish_time"])} [{e(post["format"])}]</li>'
        out += '</ul>'
    else:
        out += '<p>Nenhuma publicação agendada nos próximos dias.</p>'
    out += '<a class="button secondary" href="/calendario">Abrir calendário editorial <span aria-hidden="true">→</span></a>'
    out += '</section>'

    # 5. Bloco: Criação
    out += '<section class="panel dashboard-card">'
    out += '<span class="tag">Criação</span>'
    out += f'<h2>Campanhas recentes ({len(criacao["recent_campaigns"])})</h2>'
    if criacao['recent_campaigns']:
        out += '<ul class="dashboard-list">'
        for camp in criacao['recent_campaigns']:
            out += f'<li><a href="{e(camp["url"])}"><strong>{e(camp["title"])}</strong></a> · {e(camp["status"])} ({camp["slides_count"]} slides)</li>'
        out += '</ul>'
    else:
        out += '<p>Nenhuma campanha criada ainda.</p>'
    out += f'<p class="aside-note">Ideias fixadas: <strong>{criacao["pinned_ideas_count"]}</strong> / Total de ideias: <strong>{criacao["total_ideas_count"]}</strong></p>'
    out += '<a class="button" href="/criar">Criar nova campanha <span aria-hidden="true">+</span></a>'
    out += '</section>'

    # 6. Bloco: Aprendizados
    out += '<section class="panel dashboard-card" id="aprendizados">'
    out += '<span class="tag">Aprendizados</span>'
    out += f'<h2>Correções locais: {aprendizados["total_corrections"]} · Prompts aprovados: {aprendizados["approved_prompts_count"]}</h2>'

    if aprendizados['recent_proposals']:
        out += '<h3>Sugestões aguardando aprovação:</h3>'
        for prop in aprendizados['recent_proposals']:
            out += f'<div class="proposal-item"><p><strong>{e(prop["summary"])}</strong> (Origem: {e(prop["provenance"])})</p>'
            out += f'''<form method="post" action="/api/learning/proposals/approve" style="display:inline-block; margin-right:8px;">
                <input type="hidden" name="proposal_id" value="{e(prop["id"])}">
                <input type="hidden" name="approver" value="Diretor de Criação">
                <button type="submit">Aprovar regra</button>
            </form>
            <form method="post" action="/api/learning/proposals/reject" style="display:inline-block;">
                <input type="hidden" name="proposal_id" value="{e(prop["id"])}">
                <input type="hidden" name="reviewer" value="Diretor de Criação">
                <button type="submit" class="secondary">Rejeitar</button>
            </form></div>'''
    elif aprendizados['recent_learnings']:
        out += '<h3>Últimas correções locais registradas:</h3><ul class="dashboard-list">'
        for l in aprendizados['recent_learnings']:
            out += f'<li>{e(l["correction_note"])}</li>'
        out += '</ul>'
    else:
        out += '<p>Nenhum aprendizado ou proposta pendente no momento.</p>'

    out += '<p class="aside-note"><a href="/biblioteca?tab=prompts">Ver Prompt Library na Biblioteca →</a></p>'
    out += '</section>'

    out += '</div>'
    return out

