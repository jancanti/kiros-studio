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


def render_creator(app: Application, query: Dict[str, Any]) -> str:
    """Renderiza painel principal do Creative Director em /criar."""
    director = app.director
    ideas = app.idea_bank
    pillars = ideas.list_pillars()
    seasonal_ops = ideas.get_seasonal_opportunities()

    html = []
    html.append('<p class="eyebrow">Inteligência Estratégica</p><h1>Creative Director</h1>')
    html.append('<p class="intro">Briefings estruturados, banco de ideias com limites por pilar, sazonalidade antecipada e resolução de conflitos.</p>')

    # Mensagens e alertas
    if query.get('msg'):
        html.append(f'<p role="status" class="notice">{escape(query["msg"][0])}</p>')
    if query.get('error'):
        html.append(f'<p role="alert" class="notice warning">{escape(query["error"][0])}</p>')

    # Seção 1: Briefing Híbrido
    raw_val = escape(query.get('raw_briefing', [''])[0])
    html.append(f'''
    <div class="panel">
        <span class="tag">Briefing Híbrido</span>
        <h2>Entrada Livre com Estruturação Progressiva</h2>
        <p>Comece com linguagem livre. O Creative Director recomendará objetivos, tom e perguntas mínimas necessárias.</p>
        <form method="post" action="/api/creator/interpret_briefing" class="form-grid">
            <div class="form-group">
                <label for="briefing_text">Descreva a ideia ou objetivo da campanha</label>
                <textarea id="briefing_text" name="briefing_text" rows="3" placeholder="Ex: Quero uma campanha para mostrar minhas velas aromáticas em ambientes sofisticados e acolhedores." required>{raw_val}</textarea>
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
            <button type="submit" class="button">Interpretar Briefing</button>
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
        <div class="panel" role="region" aria-label="Resultado da estruturação">
            <span class="tag badge-success">Briefing Estruturado</span>
            <h2>Diretrizes da Campanha</h2>
            <p><strong>Objetivo Principal:</strong> <code>{p_obj.upper()}</code> (Secundário: <code>{s_obj}</code>)</p>
            <p><strong>Justificativa Estratégica:</strong> {just}</p>
            <p><strong>Confiança da Recomendação:</strong> {conf}%</p>
            <p><strong>Tom Visual Inferido:</strong> {tone}</p>
            <p><strong>Etapa do Funil:</strong> {stage} | <strong>Pilar Recomendado:</strong> {pil.capitalize()}</p>
            <form method="post" action="/api/creator/add_idea" class="inline-form" style="margin-top:14px;">
                <input type="hidden" name="title" value="Campanha: {raw_val[:50]}">
                <input type="hidden" name="concept" value="{raw_val}">
                <input type="hidden" name="pillar" value="{pil}">
                <button type="submit" class="button">Salvar como Ideia no Banco</button>
            </form>
        </div>
        ''')

    # Seção 2: Banco de Ideias por Pilar
    html.append(f'''
    <div class="panel">
        <span class="tag">Governança Editorial</span>
        <h2>Banco de Ideias ({MAX_ACTIVE_IDEAS_PER_PILLAR} ativas por pilar)</h2>
        <p>Ideias rejeitadas são arquivadas com motivo para impedir reapresentações superficiais. Ideias podem ser fixadas.</p>
        <div class="pillar-summary">
    ''')

    for p in pillars:
        pid = p['id']
        pname = p['name']
        active_count = ideas.count_active_ideas(pid)
        is_full = active_count >= MAX_ACTIVE_IDEAS_PER_PILLAR
        badge_style = 'badge-error' if is_full else 'badge-success'
        html.append(f'''
            <div class="pillar-chip">
                <strong>{pname}:</strong> <span class="tag {badge_style}">{active_count}/{MAX_ACTIVE_IDEAS_PER_PILLAR} ativas</span>
            </div>
        ''')
    html.append('</div>')

    # Formulário para adicionar nova ideia
    html.append('''
        <details class="revision" style="margin-top:18px;">
            <summary>+ Propor Nova Ideia Manualmente</summary>
            <form method="post" action="/api/creator/add_idea" class="form-grid" style="margin-top:14px;">
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
        html.append(f'<option value="{p["id"]}">{p["name"]}</option>')
    html.append('''
                    </select>
                </div>
                <div class="form-group checkbox-group">
                    <label><input type="checkbox" name="is_pinned" value="1"> Fixar ideia no topo</label>
                </div>
                <button type="submit" class="button">Adicionar Ideia</button>
            </form>
        </details>
    ''')

    # Listagem de ideias existentes
    all_ideas = ideas.list_ideas()
    if all_ideas:
        html.append('<div class="idea-cards" style="margin-top:20px;">')
        for idea in all_ideas:
            iid = escape(idea['id'])
            ititle = escape(idea['title'])
            iconcept = escape(idea['concept'])
            ipillar = escape(idea['pillar'].capitalize())
            istate = escape(idea['state'])
            ispinned = idea['is_pinned']
            rej_reason = escape(idea.get('rejection_reason') or '')

            state_badge = 'badge-success' if istate in ('approved', 'pinned') else ('badge-error' if istate == 'rejected' else 'status-active')

            html.append(f'''
            <div class="card idea-card {'idea-pinned' if ispinned else ''}">
                <div class="card-header">
                    <div>
                        <span class="tag">{ipillar}</span>
                        <h3>{ititle}</h3>
                    </div>
                    <div>
                        <span class="badge {state_badge}">{istate.upper()}</span>
                        { '<span class="tag">FIXADA</span>' if ispinned else '' }
                    </div>
                </div>
                <p>{iconcept}</p>
                { f'<p class="hint"><em>Rejeitada: {rej_reason}</em></p>' if rej_reason else '' }
                <div class="card-actions">
            ''')
            if istate != 'rejected':
                html.append(f'''
                    <form method="post" action="/api/creator/pin_idea" class="inline-form">
                        <input type="hidden" name="idea_id" value="{iid}">
                        <input type="hidden" name="pin" value="{'0' if ispinned else '1'}">
                        <button type="submit" class="button-secondary">{'Desafixar' if ispinned else 'Fixar'}</button>
                    </form>
                    <details class="inline-form">
                        <summary class="button-secondary" style="font-size:12px;padding:6px 12px;">Rejeitar com motivo</summary>
                        <form method="post" action="/api/creator/reject_idea" style="margin-top:8px;">
                            <input type="hidden" name="idea_id" value="{iid}">
                            <input name="reason" placeholder="Informe o motivo da rejeição" required style="width:250px;padding:6px;">
                            <button type="submit" class="button-danger" style="padding:6px 10px;">Confirmar rejeição</button>
                        </form>
                    </details>
                ''')
            html.append('</div></div>')
        html.append('</div>')
    html.append('</div>')

    # Seção 3: Conteúdo Adjacente com Ponte para a Marca
    html.append('''
    <div class="panel">
        <span class="tag">Topo de Funil · Descoberta</span>
        <h2>Conteúdo Adjacente e Pontes de Marca</h2>
        <p>Conteúdos de descoberta ampliam alcance dialogando com temas de interesse do público sem descaracterizar a KIROS.</p>
        <div class="adjacent-grid">
    ''')
    adjacent = ideas.generate_adjacent_content_suggestions('desaceleração e rituais')
    for adj in adjacent:
        html.append(f'''
        <div class="card" style="margin-bottom:14px;">
            <h4>{escape(adj['title'])}</h4>
            <p><strong>Por que atrai:</strong> {escape(adj['why_attracts_audience'])}</p>
            <p><strong>Relação com KIROS:</strong> {escape(adj['relation_to_brand'])}</p>
            <p><strong>Ponte para o produto:</strong> {escape(adj['bridge_to_brand'])}</p>
            <form method="post" action="/api/creator/add_adjacent">
                <input type="hidden" name="title" value="{escape(adj['title'])}">
                <input type="hidden" name="concept" value="{escape(adj['bridge_to_brand'])}">
                <input type="hidden" name="pillar" value="{adj['pillar']}">
                <button type="submit" class="button-secondary" style="font-size:12px;">Salvar no pilar {adj['pillar'].capitalize()}</button>
            </form>
        </div>
        ''')
    html.append('</div></div>')

    # Seção 4: Datas Sazonais
    html.append('''
    <div class="panel">
        <span class="tag">Planejamento Sazonal</span>
        <h2>Datas Prioritárias (2–3 Meses Antes)</h2>
        <p>Natal e Dia das Mães geram rascunhos antecipados em 4 fases, mas <strong>não entram no calendário oficial sem aprovação</strong>.</p>
        <div class="seasonal-grid">
    ''')
    for ev in seasonal_ops:
        name = escape(ev['event_name'])
        target = escape(ev['target_date'])
        days = ev['days_until']
        phase = escape(ev['current_phase'])
        html.append(f'''
        <div class="card" style="margin-bottom:12px;">
            <div class="card-header">
                <h3>{name} — {target}</h3>
                <span class="tag">Faltam {days} dias</span>
            </div>
            <p><strong>Fase Atual Sugerida:</strong> <code>{phase}</code> (Rascunho de planejamento)</p>
            <p class="hint">Fases previstas: Warm-up → Consideração → Conversão → Last Call.</p>
        </div>
        ''')
    html.append('</div></div>')

    return '\n'.join(html)

