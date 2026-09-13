"""Interface do Creative Director: briefing híbrido, banco de ideias, sazonalidade e estratégia."""
from html import escape
from typing import Any, Dict
from urllib.parse import urlencode

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.core.director import SUPPORTED_OBJECTIVES
from kiros.director.ideas import MAX_ACTIVE_IDEAS_PER_PILLAR


def dispatch_creator_action(app: Application, action: str, data: Dict[str, str]) -> str:
    """Processa ações submetidas na tela /criar via POST."""
    director = app.director
    ideas = app.idea_bank
    now_iso = director._now()

    if action == 'interpret_briefing':
        text = data.get('briefing_text', '').strip()
        custom_obj = data.get('custom_objective', '').strip()
        prov = Provenance('user', 'creator.briefing', now_iso)
        res = director.interpret_briefing(text, custom_objective=custom_obj if custom_obj else None, provenance=prov)
        
        # Checa conflitos com a marca oficial
        candidate_hints = {}
        if 'cores' in text.lower():
            candidate_hints['colors'] = 'cores informadas no briefing'
        conflicts = director.check_conflicts(candidate_hints)

        return urlencode({
            'briefing_done': '1',
            'raw_briefing': text,
            'primary_obj': res['primary_objective'],
            'secondary_obj': res['secondary_objective'],
            'justification': res['objective_justification'],
            'confidence': str(res['confidence']),
            'visual_tone': res['visual_tone'],
            'funnel_stage': res['funnel_stage'],
            'suggested_pillar': res['suggested_pillar'],
            'has_conflicts': '1' if conflicts else '0',
        })

    elif action == 'generate_ai_ideas':
        recs = director.generate_ai_recommendations(limit=3)
        return urlencode({'ideas_generated': '1', 'msg': '3 novas ideias de campanha geradas com base no seu catálogo e marca.'})

    elif action == 'use_idea':
        title = data.get('title', '').strip()
        concept = data.get('concept', '').strip()
        obj = data.get('objective', 'awareness').strip()

        briefing_text = f"Campanha: {title}. Conceito: {concept}"
        prov = Provenance('user', 'creator.use_idea', now_iso)
        res = director.interpret_briefing(briefing_text, custom_objective=obj if obj else None, provenance=prov)

        return urlencode({
            'briefing_done': '1',
            'raw_briefing': briefing_text,
            'primary_obj': res['primary_objective'],
            'secondary_obj': res['secondary_objective'],
            'justification': res['objective_justification'],
            'confidence': str(res['confidence']),
            'visual_tone': res['visual_tone'],
            'funnel_stage': res['funnel_stage'],
            'suggested_pillar': res['suggested_pillar'],
            'msg': f"Ideia '{title}' selecionada! O briefing foi estruturado automaticamente.",
        })

    elif action == 'add_idea':
        title = data.get('title', '').strip()
        concept = data.get('concept', '').strip()
        pillar = data.get('pillar', '').strip()
        is_pinned = data.get('is_pinned') == '1'
        prov = Provenance('user', 'creator.add_idea', now_iso)

        idea_id = ideas.add_idea(title, concept, pillar, provenance=prov, is_pinned=is_pinned)
        return urlencode({'saved_idea': '1', 'msg': f"Ideia '{title}' adicionada ao pilar '{pillar}'."})


    elif action == 'pin_idea':
        idea_id = data.get('idea_id', '').strip()
        pin = data.get('pin') == '1'
        ideas.pin_idea(idea_id, is_pinned=pin)
        action_txt = 'fixada' if pin else 'desafixada'
        return urlencode({'msg': f"Ideia {action_txt} com sucesso."})

    elif action == 'reject_idea':
        idea_id = data.get('idea_id', '').strip()
        reason = data.get('reason', '').strip()
        ideas.reject_idea(idea_id, reason)
        return urlencode({'msg': 'Ideia arquivada com motivo registrado para evitar repetição superficial.'})

    elif action == 'add_adjacent':
        title = data.get('title', '').strip()
        concept = data.get('concept', '').strip()
        pillar = data.get('pillar', 'lifestyle').strip()
        prov = Provenance('automatic_analysis', 'creator.adjacent', now_iso)
        ideas.add_idea(title, concept, pillar, provenance=prov)
        return urlencode({'saved_idea': '1', 'msg': f"Ideia adjacente '{title}' adicionada com sucesso."})

    raise ValueError(f"Ação desconhecida: {action}")


def render_idea_card(idea: Dict[str, Any]) -> str:
    iid = escape(idea['id'])
    ititle = escape(idea['title'])
    iconcept = escape(idea['concept'])
    ipillar = escape(idea['pillar'].capitalize())
    istate = escape(idea['state'])
    ispinned = idea.get('is_pinned', False)
    rej_reason = escape(idea.get('rejection_reason') or '')

    state_badge = 'badge-success' if istate in ('approved', 'pinned') else ('badge-error' if istate == 'rejected' else 'status-active')

    card_html = f'''
    <div class="idea-card {'idea-pinned' if ispinned else ''}" style="border:1px solid var(--hairline);border-radius:var(--radius-sm);padding:14px;background:var(--canvas);">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
            <div>
                <span class="tag" style="font-size:10px;">{ipillar}</span>
                <h4 style="margin:4px 0 2px;font-size:15px;font-weight:600;color:var(--ink);">{ititle}</h4>
            </div>
            <div class="card-badge-group">
                <span class="badge {state_badge}">{istate.upper()}</span>
                { '<span class="badge badge-pinned" style="background:var(--primary);color:#fff;margin-left:4px;">FIXADA</span>' if ispinned else '' }
            </div>
        </div>
        <p class="idea-concept-text" style="font-size:13px;color:var(--muted-blue);margin:8px 0 12px;line-height:1.5;">{iconcept}</p>
        { f'<div class="rejection-note" style="background:#fbeae5;border:1px solid #f2c7bd;padding:8px 12px;border-radius:4px;font-size:12px;color:#8a2e1d;margin-bottom:10px;"><strong>Motivo da Rejeição:</strong> <em>{rej_reason}</em></div>' if rej_reason else '' }
        <div class="card-actions" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
    '''

    if istate != 'rejected':
        card_html += f'''
            <form method="post" action="/api/creator/use_idea" class="inline-form" style="margin:0;">
                <input type="hidden" name="title" value="{ititle}">
                <input type="hidden" name="concept" value="{iconcept}">
                <button type="submit" class="button" style="margin:0;padding:6px 12px;font-size:12px;min-height:34px;">⚡ Usar no Briefing</button>
            </form>
            <form method="post" action="/api/creator/pin_idea" class="inline-form" style="margin:0;">
                <input type="hidden" name="idea_id" value="{iid}">
                <input type="hidden" name="pin" value="{'0' if ispinned else '1'}">
                <button type="submit" class="button-secondary" style="margin:0;padding:6px 12px;font-size:12px;min-height:34px;">{'Desafixar' if ispinned else 'Fixar'}</button>
            </form>
            <details class="inline-form reject-drawer" style="margin:0;">
                <summary class="button-secondary" style="font-size:12px;padding:6px 12px;min-height:34px;cursor:pointer;">Rejeitar com motivo</summary>
                <form method="post" action="/api/creator/reject_idea" class="reject-form" style="margin-top:8px;display:flex;gap:6px;">
                    <input type="hidden" name="idea_id" value="{iid}">
                    <input name="reason" placeholder="Motivo da rejeição..." required style="padding:4px 8px;font-size:12px;width:180px;">
                    <button type="submit" class="button-danger" style="padding:4px 10px;min-height:32px;font-size:11px;margin:0;">Rejeitar</button>
                </form>
            </details>
        '''

    card_html += '</div></div>'
    return card_html


def render_creator(app: Application, query: Dict[str, Any]) -> str:
    """Renderiza painel principal do Creative Director em /criar."""
    director = app.director
    ideas = app.idea_bank
    pillars = ideas.list_pillars()
    seasonal_ops = ideas.get_seasonal_opportunities()

    selected_pillar = query.get('pillar', [''])[0].strip().lower() if query.get('pillar') else ''

    html = []
    html.append('''
    <div class="creator-header">
        <h1>Creative Director</h1>
        <p class="intro">Briefings estruturados, banco de ideias com limites por pilar, sazonalidade antecipada e resolução de conflitos.</p>
    </div>
    ''')

    # Mensagens e alertas
    if query.get('msg'):
        html.append(f'<p role="status" class="notice">{escape(query["msg"][0])}</p>')
    if query.get('error'):
        html.append(f'<p role="alert" class="notice warning">{escape(query["error"][0])}</p>')

    html.append('<div class="creator-workbench">')

    # ==========================================
    # ZONA 1: Criação & Inspiração (1 Coluna - Full Width)
    # ==========================================
    html.append('<div class="creator-hero-zone">')

    # 0. Hub de Ideias Recomendadas pela IA
    ai_recs = director.generate_ai_recommendations(limit=3)
    html.append('''
    <div class="panel ai-ideas-hub">
        <div class="ai-ideas-header">
            <div class="ai-ideas-header-left">
                <span class="tag">Inteligência de Conteúdo</span>
                <h2>💡 Ideias Recomendadas para Você</h2>
            </div>
            <form method="post" action="/api/creator/generate_ai_ideas">
                <input type="hidden" name="action" value="generate">
                <button type="submit" class="button-secondary" style="font-size: 13px;">✨ Gerar Novas Ideias</button>
            </form>
        </div>
        <p style="color: var(--muted-blue); font-size: 14px; margin-bottom: 16px;">A IA analisou seus produtos cadastrados e sua marca para sugerir campanhas prontas de alta conversão. Clique no botão de 1-Clique para iniciar:</p>
        <div class="ai-ideas-grid">
    ''')

    for rec in ai_recs:
        theme = escape(rec['theme'])
        title = escape(rec['title'])
        concept = escape(rec['concept'])
        obj = escape(rec['objective'])
        fmt = escape(rec['format'])
        p_name = escape(rec.get('product_name', 'Produto KIROS'))

        theme_bg = '#693edf' if 'Estética' in theme else ('#10a37f' if 'Ingredientes' in theme else '#e1306c')

        html.append(f'''
        <div class="card ai-idea-card">
            <div>
                <div class="ai-idea-card-header">
                    <span class="tag" style="background: {theme_bg}; color: white; font-size: 11px; padding: 2px 8px; border-radius: 4px;">{theme}</span>
                    <small style="color: var(--muted-blue); font-size: 11px;">{fmt}</small>
                </div>
                <h3>{title}</h3>
                <p>{concept}</p>
            </div>
            <form method="post" action="/api/creator/use_idea">
                <input type="hidden" name="title" value="{title}">
                <input type="hidden" name="concept" value="{concept}">
                <input type="hidden" name="objective" value="{obj}">
                <button type="submit" class="button" style="width: 100%; padding: 8px 12px; font-size: 13px; text-align: center;">⚡ Criar esta Campanha em 1-Clique</button>
            </form>
        </div>
        ''')

    html.append('''
        </div>
    </div>
    ''')

    # 1. Briefing Híbrido
    raw_val = escape(query.get('raw_briefing', [''])[0])
    html.append(f'''
    <div class="briefing-canvas" id="briefing-canvas">
        <span class="tag">Briefing Híbrido</span>
        <h2>Entrada Livre com Estruturação Progressiva</h2>
        <p>Comece com linguagem livre ou edite a ideia selecionada acima. O Creative Director recomendará objetivos e tom.</p>


        <div class="quick-chips-container">
            <span class="quick-chips-label">Sugestões de pauta rápida:</span>
            <div class="quick-chips">
                <button type="button" class="quick-chip" onclick="setQuickBriefing(this, 'Quero uma campanha para destacar a vela de alecrim como ancoragem de foco no home office.');">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/></svg>
                    <span>Foco &amp; Alecrim</span>
                </button>
                <button type="button" class="quick-chip" onclick="setQuickBriefing(this, 'Campanha mostrando o ritual de acender a vela antes de ler um livro à noite, desacelerando das telas.');">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
                    <span>Ritual Noturno</span>
                </button>
                <button type="button" class="quick-chip" onclick="setQuickBriefing(this, 'Lançamento da nova linha de difusores em vidro âmbar com estética escandinava e minimalista.');">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                    <span>Linha Âmbar</span>
                </button>
                <button type="button" class="quick-chip" onclick="setQuickBriefing(this, 'Ritual matinal acolhedor destacando aromas cítricos e flor de laranjeira para despertar intenções.');">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
                    <span>Manhã de Renovação</span>
                </button>
            </div>
        </div>

        <form method="post" action="/api/creator/interpret_briefing" class="briefing-form">
            <div class="form-group">
                <label for="briefing_text">Descreva a ideia ou objetivo da campanha</label>
                <textarea id="briefing_text" name="briefing_text" rows="3" placeholder="Ex: Quero uma campanha para mostrar minhas velas aromáticas em ambientes sofisticados e acolhedores." required>{raw_val}</textarea>
                <div class="textarea-assist">
                    <span class="hint">Linguagem natural: o estúdio traduz em objetivos, tom e funil editorial.</span>
                    <span class="hint">Atalho: <kbd>Cmd</kbd>+<kbd>Enter</kbd></span>
                </div>
            </div>
            <div class="form-group">
                <label for="custom_objective">Objetivo específico (opcional, ou deixe o Diretor recomendar)</label>
                <select id="custom_objective" name="custom_objective">
                    <option value="">Recomendar automaticamente</option>
    ''')
    for obj in SUPPORTED_OBJECTIVES:
        html.append(f'<option value="{obj}">{obj.capitalize()}</option>')
    html.append('''
                </select>
            </div>
            <button type="submit" class="button">Interpretar Briefing <span aria-hidden="true">→</span></button>
        </form>
    </div>
    ''')

    # Resultado da interpretação
    if query.get('briefing_done'):
        p_obj = escape(query.get('primary_obj', [''])[0])
        s_obj = escape(query.get('secondary_obj', [''])[0])
        just = escape(query.get('justification', [''])[0])
        conf = int(float(query.get('confidence', ['0.8'])[0]) * 100)
        tone = escape(query.get('visual_tone', [''])[0])
        stage = escape(query.get('funnel_stage', [''])[0])
        pil = escape(query.get('suggested_pillar', [''])[0])

        html.append(f'''
        <div class="briefing-result-card" role="region" aria-label="Resultado da estruturação">
            <div class="briefing-result-header">
                <div>
                    <span class="tag badge-success">Briefing Estruturado</span>
                    <h2>Diretrizes da Campanha</h2>
                </div>
                <div class="confidence-indicator">
                    <span class="badge badge-success">{conf}% de Confiança</span>
                    <div class="confidence-track" aria-hidden="true">
                        <div class="confidence-bar" style="width:{conf}%;"></div>
                    </div>
                </div>
            </div>
            <div class="briefing-meta-grid">
                <div class="briefing-meta-item">
                    <strong>Objetivo Principal</strong>
                    <code>{p_obj.upper()}</code> <span class="hint">(Secundário: <code>{s_obj}</code>)</span>
                </div>
                <div class="briefing-meta-item">
                    <strong>Confiança da Recomendação</strong>
                    <span class="badge badge-success">{conf}%</span>
                </div>
                <div class="briefing-meta-item">
                    <strong>Tom Visual Inferido</strong>
                    <span>{tone}</span>
                </div>
                <div class="briefing-meta-item">
                    <strong>Etapa do Funil &amp; Pilar</strong>
                    <span>{stage} · <strong>{pil.capitalize()}</strong></span>
                </div>
            </div>
            <div class="briefing-justification-box">
                <p><strong>Justificativa Estratégica:</strong> {just}</p>
            </div>
            <form method="post" action="/api/creator/add_idea" class="inline-form" style="margin-top:16px;">
                <input type="hidden" name="title" value="Campanha: {raw_val[:50]}">
                <input type="hidden" name="concept" value="{raw_val}">
                <input type="hidden" name="pillar" value="{pil}">
                <button type="submit" class="button">Salvar como Ideia no Banco <span aria-hidden="true">+</span></button>
            </form>
        </div>
        ''')

    # Fecha Zona 1 (1 Coluna Full Width)
    html.append('</div>') # fecha creator-hero-zone

    # ==========================================
    # ZONA 2: Apoio & Governança (2 Colunas: 50% / 50%)
    # ==========================================
    html.append('<div class="creator-secondary-grid">')

    # Coluna Esquerda: Banco de Ideias & Governança Editorial
    html.append('<div class="creator-column-left">')

    # 2. Banco de Ideias por Pilar (Accordions Aninhados por Governança Editorial)
    all_ideas = ideas.list_ideas()

    html.append(f'''
    <div class="panel" id="banco-de-ideias">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
            <div>
                <span class="tag">Governança Editorial</span>
                <h2 style="margin:4px 0 6px;">Banco de Ideias ({MAX_ACTIVE_IDEAS_PER_PILLAR} ativas por pilar)</h2>
                <p style="margin:0 0 12px;">Ideias categorizadas em accordions por pilar e estado. Ideias rejeitadas são arquivadas com motivo para impedir reapresentações superficiais.</p>
            </div>
        </div>

        <div class="idea-filter-bar">
            <a href="/criar#banco-de-ideias" class="idea-filter-tab {'active' if not selected_pillar else ''}">
                Todos ({len(all_ideas)})
            </a>
    ''')
    for p in pillars:
        pid = p['id']
        pname = p['name']
        pcount = len([i for i in all_ideas if i['pillar'].lower() == pid.lower()])
        is_sel = selected_pillar == pid.lower()
        html.append(f'''
            <a href="/criar?pillar={pid}#banco-de-ideias" class="idea-filter-tab {'active' if is_sel else ''}">
                {pname} ({pcount})
            </a>
        ''')
    html.append('''
        </div>
    ''')

    if selected_pillar:
        matching_pillar = next((p['name'] for p in pillars if p['id'].lower() == selected_pillar), selected_pillar.capitalize())
        html.append(f'''
        <div class="filter-active-indicator">
            <span>Filtrando ideias por <strong>{matching_pillar}</strong></span>
            <a href="/criar#banco-de-ideias" class="clear-filter-link">Ver todos os pilares ✕</a>
        </div>
        ''')

    html.append(f'''
        <details class="revision idea-form-drawer" style="margin-bottom:16px;">
            <summary>+ Propor Nova Ideia Manualmente</summary>
            <form method="post" action="/api/creator/add_idea" class="idea-manual-form">
                <div class="form-group">
                    <label for="idea_title">Título da Ideia</label>
                    <input id="idea_title" name="title" placeholder="Ex: Rituais de Outono com Alecrim" required>
                </div>
                <div class="form-group">
                    <label for="idea_concept">Conceito e narrativa</label>
                    <textarea id="idea_concept" name="concept" rows="2" placeholder="Descreva a ambientação e mensagem central" required></textarea>
                </div>
                <div class="form-group">
                    <label for="idea_pillar">Pilar</label>
                    <select id="idea_pillar" name="pillar" required>
    ''')
    for p in pillars:
        selected_attr = ' selected' if selected_pillar == p['id'].lower() else ''
        html.append(f'<option value="{p["id"]}"{selected_attr}>{p["name"]}</option>')
    html.append('''
                    </select>
                </div>
                <div class="form-group checkbox-group">
                    <label><input type="checkbox" name="is_pinned" value="1"> Fixar ideia no topo</label>
                </div>
                <button type="submit" class="button">Adicionar Ideia <span aria-hidden="true">+</span></button>
            </form>
        </details>
    ''')

    # Renderização por Accordions Aninhados
    if all_ideas:
        html.append('<div class="nested-accordions-container" style="margin-top:16px;">')
        for p in pillars:
            pid = p['id']
            pname = p['name']
            p_ideas = [i for i in all_ideas if i['pillar'].lower() == pid.lower()]
            active_ideas = [i for i in p_ideas if i.get('state') != 'rejected']
            rejected_ideas = [i for i in p_ideas if i.get('state') == 'rejected']

            # Se houver filtro ativo e este pilar não for o selecionado, ignora
            if selected_pillar and pid.lower() != selected_pillar:
                continue

            active_cnt = len(active_ideas)
            is_full = active_cnt >= MAX_ACTIVE_IDEAS_PER_PILLAR
            badge_cls = 'badge-error' if is_full else 'badge-success'
            is_open = 'open' if (selected_pillar == pid.lower() or active_cnt > 0) else ''

            html.append(f'''
            <details class="pillar-accordion" {is_open}>
                <summary class="pillar-summary-bar">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <strong style="color:var(--ink);">{pname}</strong>
                        <span class="tag" style="font-size:11px;">{len(p_ideas)} pauta(s)</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span class="badge {badge_cls}">{active_cnt}/{MAX_ACTIVE_IDEAS_PER_PILLAR} ativas</span>
                        <span style="font-size:12px;color:var(--muted)">▼</span>
                    </div>
                </summary>
                <div class="pillar-content">
            ''')

            # Sub-accordion 1: Ideias Ativas e Fixadas
            if active_ideas:
                html.append(f'''
                <details class="subgroup-accordion" open>
                    <summary class="subgroup-summary">
                        📌 Ideias Ativas &amp; Em Destaque ({len(active_ideas)})
                    </summary>
                    <div class="subgroup-content">
                ''')
                for idea in active_ideas:
                    html.append(render_idea_card(idea))
                html.append('</div></details>')
            else:
                html.append('<p class="hint" style="margin:8px 0;">Nenhuma ideia ativa neste pilar.</p>')

            # Sub-accordion 2: Ideias Rejeitadas & Arquivadas
            if rejected_ideas:
                html.append(f'''
                <details class="subgroup-accordion">
                    <summary class="subgroup-summary" style="background:#fff5f2;color:#8a2e1d;">
                        📁 Histórico de Ideias Rejeitadas ({len(rejected_ideas)})
                    </summary>
                    <div class="subgroup-content">
                ''')
                for idea in rejected_ideas:
                    html.append(render_idea_card(idea))
                html.append('</div></details>')

            html.append('</div></details>')
        html.append('</div>')
    else:
        html.append('''
        <div class="empty-idea-state">
            <p>Nenhuma ideia cadastrada no momento.</p>
            <span class="hint">Use as sugestões rápidas acima ou adicione uma nova ideia.</span>
        </div>
        ''')

    html.append('</div>') # fecha banco-de-ideias panel
    html.append('</div>') # fecha creator-column-left

    # ==========================================
    # COLUNA DIREITA: Radar Estratégico & Governança (50%)
    # ==========================================
    html.append('<div class="creator-column-right">')

    # Mini-painel: Governança dos 6 Pilares
    html.append(f'''
    <div class="panel">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;">
            <div>
                <span class="tag">Governança de Pautas</span>
                <h3 style="margin:6px 0 4px;font-size:18px;">Capacidade dos Pilares</h3>
            </div>
            {f'<a href="/criar#banco-de-ideias" class="clear-filter-link" style="font-size:12px;">Ver todos</a>' if selected_pillar else ''}
        </div>
        <p style="font-size:12px;margin:0 0 12px;color:var(--muted-blue);">Monitoramento de cotas para garantir equilíbrio editorial.</p>
        <div class="pillar-mini-grid">
    ''')
    for p in pillars:
        pid = p['id']
        pname = p['name']
        active_count = ideas.count_active_ideas(pid)
        is_full = active_count >= MAX_ACTIVE_IDEAS_PER_PILLAR
        badge_style = 'badge-error' if is_full else 'badge-success'
        is_active_card = selected_pillar == pid.lower()
        segments_html = ''.join(f'<div class="pillar-segment {"filled" if i < active_count else ""}"></div>' for i in range(MAX_ACTIVE_IDEAS_PER_PILLAR))
        html.append(f'''
            <a href="/criar?pillar={pid}#banco-de-ideias" class="pillar-mini-card {'active-pillar' if is_active_card else ''}" title="Filtrar por {pname}">
                <div class="pillar-mini-header">
                    <span class="pillar-mini-name">{pname}</span>
                    <span class="pillar-quota-badge {badge_style}">{active_count}/{MAX_ACTIVE_IDEAS_PER_PILLAR} ativas</span>
                </div>
                <div class="pillar-segments" aria-hidden="true">
                    {segments_html}
                </div>
            </a>
        ''')
    html.append('</div></div>')

    # Radar Sazonal
    html.append('''
    <div class="panel">
        <span class="tag">Planejamento Sazonal</span>
        <h3 style="margin:6px 0 4px;font-size:18px;">Datas Prioritárias (2–3 Meses Antes)</h3>
        <p style="font-size:12px;margin:0 0 12px;color:var(--muted-blue);">Natal e Dia das Mães geram rascunhos antecipados em 4 fases, mas <strong>não entram no calendário oficial sem aprovação</strong>.</p>
        <div class="seasonal-grid">
    ''')
    for ev in seasonal_ops:
        name = escape(ev['event_name'])
        target = escape(ev['target_date'])
        days = ev['days_until']
        phase = escape(ev['current_phase'])
        html.append(f'''
        <div class="seasonal-item-card">
            <div class="card-header">
                <h4 style="margin:0;font-size:14px;font-weight:600;">{name}</h4>
                <span class="tag" style="color:var(--color-primary);font-weight:600;">Faltam {days} dias</span>
            </div>
            <p style="font-size:12px;margin:6px 0 10px;color:var(--muted-blue);">Data: <strong>{target}</strong> · Fase: <code>{phase}</code></p>
            <div class="seasonal-phase-meter" aria-label="Fase atual: {phase}">
                <div class="phase-segments">
                    <span class="phase-seg {'active' if phase == 'Warm-up' else 'done' if phase in ('Consideração', 'Conversão', 'Last Call') else ''}"></span>
                    <span class="phase-seg {'active' if phase == 'Consideração' else 'done' if phase in ('Conversão', 'Last Call') else ''}"></span>
                    <span class="phase-seg {'active' if phase == 'Conversão' else 'done' if phase == 'Last Call' else ''}"></span>
                    <span class="phase-seg {'active' if phase == 'Last Call' else ''}"></span>
                </div>
                <div class="phase-label-row">
                    <span class="phase-current-tag">Fase ativa: <strong>{phase}</strong></span>
                    <span class="phase-step-count">{'1/4' if phase == 'Warm-up' else ('2/4' if phase == 'Consideração' else ('3/4' if phase == 'Conversão' else '4/4'))}</span>
                </div>
            </div>
            <p class="hint" style="margin:0 0 12px;">Fases previstas: Warm-up → Consideração → Conversão → Last Call.</p>
            <button type="button" class="button-secondary" style="width:100%;font-size:12px;padding:8px 12px;min-height:36px;" onclick="useSeasonalPauta('Campanha sazonal de {name} ({target}): desenvolvimento de narrativa para a fase de {phase}.');">Usar como Pauta no Briefing ↑</button>
        </div>
        ''')
    html.append('</div></div>')

    # Conteúdo Adjacente e Pontes de Marca
    html.append('''
    <div class="panel">
        <span class="tag">Topo de Funil · Descoberta</span>
        <h3 style="margin:6px 0 4px;font-size:18px;">Conteúdo Adjacente e Pontes de Marca</h3>
        <p style="font-size:12px;margin:0 0 12px;color:var(--muted-blue);">Conteúdos de descoberta ampliam alcance dialogando com temas de interesse do público sem descaracterizar a KIROS.</p>
        <div class="adjacent-grid">
    ''')
    adjacent = ideas.generate_adjacent_content_suggestions('desaceleração e rituais')
    for adj in adjacent:
        atitle = escape(adj['title'])
        awhy = escape(adj['why_attracts_audience'])
        arelation = escape(adj['relation_to_brand'])
        abridge = escape(adj['bridge_to_brand'])
        apillar = adj['pillar']
        html.append(f'''
        <div class="adjacent-discovery-card">
            <div class="card-header">
                <h4>{atitle}</h4>
                <span class="tag">{apillar.capitalize()}</span>
            </div>
            <div class="adjacent-bridge-flow">
                <div class="adjacent-row">
                    <strong>Por que atrai:</strong> {awhy}
                </div>
                <div class="adjacent-row">
                    <strong>Relação com KIROS:</strong> {arelation}
                </div>
                <div class="adjacent-row bridge-highlight">
                    <strong>Ponte para o produto:</strong> {abridge}
                </div>
            </div>
            <form method="post" action="/api/creator/add_adjacent">
                <input type="hidden" name="title" value="{atitle}">
                <input type="hidden" name="concept" value="{abridge}">
                <input type="hidden" name="pillar" value="{apillar}">
                <button type="submit" class="button-secondary" style="width:100%;font-size:12px;padding:8px 12px;min-height:36px;">Salvar no pilar {apillar.capitalize()}</button>
            </form>
        </div>
        ''')
    html.append('</div></div>')

    html.append('</div>') # fecha creator-column-right
    html.append('</div>') # fecha creator-secondary-grid
    html.append('</div>') # fecha creator-workbench

    # Script com micro-interações do Studio
    html.append('''
    <script>
    function setQuickBriefing(btn, text) {
        var ta = document.getElementById('briefing_text');
        if (ta) {
            ta.value = text;
            ta.focus();
            document.querySelectorAll('.quick-chip').forEach(function(c) { c.classList.remove('active'); });
            btn.classList.add('active');
        }
    }
    function useSeasonalPauta(text) {
        var ta = document.getElementById('briefing_text');
        var canvas = document.getElementById('briefing-canvas');
        if (ta && canvas) {
            ta.value = text;
            canvas.scrollIntoView({ behavior: 'smooth', block: 'start' });
            canvas.classList.add('briefing-pulse');
            setTimeout(function() {
                canvas.classList.remove('briefing-pulse');
                ta.focus();
            }, 600);
        }
    }
    document.addEventListener('DOMContentLoaded', function() {
        var ta = document.getElementById('briefing_text');
        if (ta) {
            ta.addEventListener('keydown', function(e) {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault();
                    if (this.form) {
                        this.form.submit();
                    }
                }
            });
        }
    });
    </script>
    ''')

    return '\n'.join(html)

