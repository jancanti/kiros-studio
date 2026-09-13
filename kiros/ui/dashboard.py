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

    out = '<div class="dashboard-header">'
    out += '<div class="dashboard-header-top">'
    out += '<div>'
    out += '<p class="eyebrow">Dashboard Contextual · Visão Geral do Estúdio · KIROS V1</p>'
    out += '<p class="intro">Esteira KIROS para Instagram (@usekiros): Hub de Ideias, Cadastro de Produtos, Aprovação Visual e Agendamento Simplificado.</p>'
    out += '</div>'
    out += '<div class="dashboard-header-actions">'
    out += '<a class="button button-primary" href="/criar">Criar Nova Campanha <span aria-hidden="true">+</span></a>'
    out += '<a class="button button-secondary" href="/criar#banco-de-ideias">Hub de Ideias</a>'
    out += '</div>'
    out += '</div>'
    out += '</div>'

    # Barra Slim Horizontal de Métricas & Status da Fila
    is_paused = hoje['queue_paused']
    queue_badge_class = 'dashboard-queue-badge paused' if is_paused else 'dashboard-queue-badge'
    queue_dot = '⏸️' if is_paused else '🟢'
    queue_text = 'Fila Pausada' if is_paused else f'Fila {e(hoje["queue_status"])}'

    out += '<div class="dashboard-metrics-bar">'
    out += '<div class="dashboard-metrics-group">'
    out += f'<div class="dashboard-metrics-item"><strong>{hoje["completed_jobs"]}</strong> <span>Jobs Concluídos</span></div>'
    out += '<span style="color:var(--hairline);">·</span>'
    out += f'<div class="dashboard-metrics-item"><strong>{len(criacao["recent_campaigns"])}</strong> <span>Campanhas</span></div>'
    out += '<span style="color:var(--hairline);">·</span>'
    out += f'<div class="dashboard-metrics-item"><strong>{calendario["scheduled_count"]}</strong> <span>Agendados</span></div>'
    out += '<span style="color:var(--hairline);">·</span>'
    out += f'<div class="dashboard-metrics-item"><strong>{aprendizados["approved_prompts_count"]}</strong> <span>Prompts Ativos</span></div>'
    out += '</div>'

    out += '<div class="dashboard-metrics-queue">'
    out += f'<span class="{queue_badge_class}">{queue_dot} {queue_text}</span>'
    if is_paused:
        out += '<form method="post" action="/api/command" style="margin:0;"><input type="hidden" name="command" value="Retome a geração"><button type="submit" class="button">Retomar Fila</button></form>'
    else:
        out += '<form method="post" action="/api/command" style="margin:0;"><input type="hidden" name="command" value="Pause a geração"><button type="submit" class="button-secondary">Pausar Fila</button></form>'
    out += '</div>'
    out += '</div>'

    if query.get('notice'):
        out += f'<p class="notice" role="status">{e(query["notice"][0])}</p>'
    if query.get('error'):
        out += f'<p class="notice" role="alert">{e(query["error"][0])}</p>'

    # Grid calibrado (3 colunas desktop / 2 tablet / 1 mobile) com cards proporcionais
    out += '<div class="dashboard-grid">'

    # 1. Bloco: Hoje
    out += '<section class="panel dashboard-card">'
    out += '<div class="dashboard-card-body">'
    out += '<span class="tag">Hoje</span>'
    out += f'<h2>{e(hoje["data_formatada"])}</h2>'
    queue_dot_mini = '🟢' if not hoje['queue_paused'] else '⏸️'
    out += f'<div class="dashboard-card-meta"><span>{queue_dot_mini} <strong>Fila {e(hoje["queue_status"])}</strong></span><span>·</span><span>{hoje["pending_jobs"]} pendentes</span><span>·</span><span>{hoje["completed_jobs"]} concluídas</span></div>'
    out += '</div>'
    out += '<div class="dashboard-card-footer">'
    if hoje['queue_paused']:
        out += '<form method="post" action="/api/command" style="margin:0;width:100%;"><input type="hidden" name="command" value="Retome a geração"><button type="submit" class="button">Retomar fila</button></form>'
    else:
        out += '<form method="post" action="/api/command" style="margin:0;width:100%;"><input type="hidden" name="command" value="Pause a geração"><button type="submit" class="button-secondary">Pausar fila</button></form>'
    out += '</div>'
    out += '</section>'

    # 2. Bloco: Oportunidade
    out += '<section class="panel dashboard-card">'
    out += '<div class="dashboard-card-body">'
    out += f'<div style="display:flex;justify-content:space-between;align-items:center;"><span class="tag">Oportunidade</span><span class="aside-note" style="font-size:11px;color:var(--muted-blue);">Pilar: <strong>{e(oportunidade["recommended_pillar"])}</strong></span></div>'
    out += f'<h2>{e(oportunidade["title"])}</h2>'
    out += f'<p class="dashboard-card-desc">{e(oportunidade["description"])}</p>'
    out += '</div>'
    out += '<div class="dashboard-card-footer">'
    out += f'<a class="button button-secondary" href="{e(oportunidade.get("target_url", "/criar"))}">Explorar oportunidade <span aria-hidden="true">→</span></a>'
    out += '</div>'
    out += '</section>'

    # 3. Bloco: Próximo passo recomendado
    out += '<section class="panel dashboard-card highlight-step">'
    out += '<div class="dashboard-card-body">'
    out += f'<div style="display:flex;justify-content:space-between;align-items:center;"><span class="tag priority-{e(proximo_passo["priority"])}">Próximo passo recomendado</span><span class="aside-note" style="font-size:11px;text-transform:capitalize;">Prioridade {e(proximo_passo["priority"])}</span></div>'
    out += f'<h2>{e(proximo_passo["action_label"])}</h2>'
    out += f'<p class="dashboard-card-desc">{e(proximo_passo["description"])}</p>'
    out += '</div>'
    out += '<div class="dashboard-card-footer">'
    out += f'<a class="button button-primary" href="{e(proximo_passo["url"])}">Executar ação recomendada <span aria-hidden="true">→</span></a>'
    out += '</div>'
    out += '</section>'

    # 4. Bloco: Calendário
    out += '<section class="panel dashboard-card">'
    out += '<div class="dashboard-card-body">'
    out += f'<div style="display:flex;justify-content:space-between;align-items:center;"><span class="tag">Calendário</span><span class="aside-note" style="font-size:11px;color:var(--muted-blue);">{calendario["scheduled_count"]} na fila</span></div>'
    out += f'<h2>Postagens agendadas: {calendario["scheduled_count"]}</h2>'
    if calendario['upcoming_posts']:
        out += '<ul class="dashboard-list">'
        for post in calendario['upcoming_posts'][:2]:
            out += f'<li><strong>{e(post["title"])}</strong> · {e(post["publish_time"][:10])}</li>'
        out += '</ul>'
    else:
        out += '<p class="dashboard-card-desc" style="color:var(--muted-blue);">Nenhuma publicação agendada nos próximos dias.</p>'
    out += '</div>'
    out += '<div class="dashboard-card-footer">'
    out += '<a class="button button-secondary" href="/calendario">Abrir calendário editorial <span aria-hidden="true">→</span></a>'
    out += '</div>'
    out += '</section>'

    # 5. Bloco: Criação
    out += '<section class="panel dashboard-card">'
    out += '<div class="dashboard-card-body">'
    out += f'<div style="display:flex;justify-content:space-between;align-items:center;"><span class="tag">Criação</span><span class="aside-note" style="font-size:11px;color:var(--muted);">Ideias: {criacao["pinned_ideas_count"]} fixadas · {criacao["total_ideas_count"]} total</span></div>'
    out += f'<h2>Campanhas recentes ({len(criacao["recent_campaigns"])})</h2>'
    if criacao['recent_campaigns']:
        out += '<ul class="dashboard-list">'
        for camp in criacao['recent_campaigns'][:2]:
            out += f'<li><a href="{e(camp["url"])}"><strong>{e(camp["title"])}</strong></a> · {e(camp["status"])}</li>'
        out += '</ul>'
    else:
        out += '<p class="dashboard-card-desc" style="color:var(--muted-blue);">Nenhuma campanha criada ainda.</p>'
    out += '</div>'
    out += '<div class="dashboard-card-footer">'
    out += '<a class="button" href="/criar">Criar nova campanha <span aria-hidden="true">+</span></a>'
    out += '</div>'
    out += '</section>'

    # 6. Bloco: Aprendizados
    out += '<section class="panel dashboard-card" id="aprendizados">'
    out += '<div class="dashboard-card-body">'
    out += f'<div style="display:flex;justify-content:space-between;align-items:center;"><span class="tag">Aprendizados</span><span class="aside-note" style="font-size:11px;color:var(--muted);">{aprendizados["approved_prompts_count"]} prompts</span></div>'
    out += '<h2>Aprendizados &amp; Prompts</h2>'
    out += f'<div class="dashboard-card-meta"><span>{aprendizados["total_corrections"]} correções locais</span><span>·</span><span>{aprendizados["approved_prompts_count"]} prompts validados</span></div>'

    if aprendizados['recent_proposals']:
        out += '<div style="margin-top:6px;">'
        for prop in aprendizados['recent_proposals'][:1]:
            out += f'<div class="proposal-item" style="padding:8px 10px;margin:6px 0;"><p style="font-size:12px;margin:0 0 6px;"><strong>{e(prop["summary"])}</strong></p>'
            out += f'''<form method="post" action="/api/learning/proposals/approve" style="display:inline-block; margin-right:6px;">
                <input type="hidden" name="proposal_id" value="{e(prop["id"])}">
                <input type="hidden" name="approver" value="Diretor de Criação">
                <button type="submit" style="padding:4px 8px;font-size:11px;min-height:28px;">Aprovar</button>
            </form>
            <form method="post" action="/api/learning/proposals/reject" style="display:inline-block;">
                <input type="hidden" name="proposal_id" value="{e(prop["id"])}">
                <input type="hidden" name="reviewer" value="Diretor de Criação">
                <button type="submit" class="button-secondary" style="padding:4px 8px;font-size:11px;min-height:28px;">Rejeitar</button>
            </form></div>'''
        out += '</div>'
    elif aprendizados['recent_learnings']:
        out += '<ul class="dashboard-list">'
        for l in aprendizados['recent_learnings'][:2]:
            out += f'<li>{e(l["correction_note"])}</li>'
        out += '</ul>'
    else:
        out += '<p class="dashboard-card-desc" style="color:var(--muted-blue);">Nenhuma proposta ou correção pendente.</p>'
    out += '</div>'
    out += '<div class="dashboard-card-footer">'
    out += '<a class="button button-secondary" href="/biblioteca?tab=prompts">Ver Prompt Library <span aria-hidden="true">→</span></a>'
    out += '</div>'
    out += '</section>'

    out += '</div>'
    return out

