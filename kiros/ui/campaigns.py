"""Interface de Campanhas, Storyboard, Pipeline e Tela de Aprovação (Seções 10, 23, 31, 56, 66, 75)."""
from html import escape
import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from kiros.application import Application
from kiros.campaigns.models import UnapprovedExecutionError
from kiros.core.contracts import Provenance


def dispatch_campaign_action(app: Application, action: str, data: Dict[str, str]) -> str:
    """Processa ações submetidas em /conteudo via POST."""
    mgr = app.campaigns
    director = app.director

    if action == 'create':
        title = data.get('title', '').strip()
        briefing_text = data.get('briefing_text', '').strip()
        custom_obj = data.get('custom_objective', '').strip()
        approval_mode = data.get('approval_mode', 'minimal').strip()

        if not title:
            title = f"Campanha: {briefing_text[:40]}" if briefing_text else "Nova Campanha KIROS"

        # Interpretação inicial com o CreativeDirector se houver texto
        if briefing_text:
            briefing = director.interpret_briefing(briefing_text, custom_objective=custom_obj if custom_obj else None)
        else:
            briefing = {
                'raw_briefing': title,
                'summary': title,
                'primary_objective': custom_obj or 'awareness',
                'secondary_objective': 'relacionamento',
                'visual_tone': 'Minimalista, acolhedor e contemporâneo',
                'confidence': 0.90,
            }

        # Seleção de produtos pelo conceito
        products = director.select_products_for_concept(briefing.get('summary', title))

        strategy = {
            'funnel_stage': briefing.get('funnel_stage', 'Descoberta'),
            'suggested_pillar': briefing.get('suggested_pillar', 'produtos'),
        }

        cid = mgr.create_campaign(
            title=title,
            briefing=briefing,
            strategy=strategy,
            products=products,
            approval_mode=approval_mode,
            provenance=Provenance('user', 'campaigns.create', director._now()),
        )

        # Gera 3 slides conceituais iniciais com o Creative Director
        concept_slides = director.create_storyboard_concept(
            briefing_text=briefing.get('summary', title),
            visual_tone=briefing.get('visual_tone', ''),
            num_slides=3,
        )
        for s in concept_slides:
            mgr.add_storyboard_slide(
                campaign_id=cid,
                title=s['title'],
                visual_prompt=s['visual_prompt'],
                framing=s['framing'],
                caption_draft=s['caption_draft'],
                engine_override=s['engine_override'],
            )

        return urlencode({'campaign_id': cid, 'msg': f"Campanha '{title}' criada com 3 slides no storyboard."})

    elif action == 'add_slide':
        cid = data.get('campaign_id', '').strip()
        title = data.get('title', '').strip()
        prompt = data.get('visual_prompt', '').strip()
        framing = data.get('framing', 'medium').strip()
        caption = data.get('caption_draft', '').strip()
        engine = data.get('engine_override', '').strip() or None

        mgr.add_storyboard_slide(
            campaign_id=cid,
            title=title,
            visual_prompt=prompt,
            framing=framing,
            caption_draft=caption,
            engine_override=engine,
        )
        return urlencode({'campaign_id': cid, 'msg': f"Slide '{title}' adicionado ao storyboard."})

    elif action == 'update_step':
        step_id = data.get('step_id', '').strip()
        cid = data.get('campaign_id', '').strip()
        name = data.get('name', '').strip()
        prov_id = data.get('provider_id', '').strip()
        mod_id = data.get('model_id', '').strip()

        mgr.update_pipeline_step(
            step_id=step_id,
            name=name if name else None,
            provider_id=prov_id if prov_id else None,
            model_id=mod_id if mod_id else None,
        )
        return urlencode({
            'campaign_id': cid,
            'msg': 'Etapa atualizada. Mudança material invalidou aprovações prévias e incrementou versão do plano.',
        })

    elif action == 'update_slide_engine':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        engine = data.get('engine_override', '').strip()

        mgr.update_slide_engine(slide_id, engine)
        return urlencode({
            'campaign_id': cid,
            'msg': 'Motor do slide atualizado preservando os demais slides.',
        })

    elif action == 'submit_approval':
        cid = data.get('campaign_id', '').strip()
        mgr.submit_for_approval(cid)
        return urlencode({'campaign_id': cid, 'msg': 'Campanha submetida para revisão e aprovação formal.'})

    elif action == 'approve':
        cid = data.get('campaign_id', '').strip()
        approver = data.get('approver', 'Diretoria Criativa').strip()
        mgr.approve_campaign(cid, approver=approver)
        return urlencode({'campaign_id': cid, 'msg': f'Plano de execução aprovado com sucesso por {approver}.'})

    elif action == 'approve_step':
        cid = data.get('campaign_id', '').strip()
        step_id = data.get('step_id', '').strip()
        approver = data.get('approver', 'Diretoria Criativa').strip()
        mgr.approve_step(step_id, approver=approver)
        return urlencode({'campaign_id': cid, 'msg': f'Etapa aprovada com sucesso por {approver}.'})

    elif action == 'queue':
        cid = data.get('campaign_id', '').strip()
        try:
            mgr.queue_execution(cid)
            return urlencode({'campaign_id': cid, 'msg': 'Campanha enfileirada na fila de execução com sucesso.'})
        except UnapprovedExecutionError as exc:
            return urlencode({'campaign_id': cid, 'error': str(exc)})

    elif action == 'pause':
        cid = data.get('campaign_id', '').strip()
        mgr.pause_campaign(cid)
        return urlencode({'campaign_id': cid, 'msg': 'Execução pausada. Trabalhos concluídos foram preservados.'})

    elif action == 'resume':
        cid = data.get('campaign_id', '').strip()
        mgr.resume_campaign(cid)
        return urlencode({'campaign_id': cid, 'msg': 'Execução retomada sem duplicação de etapas concluídas.'})

    elif action == 'cancel':
        cid = data.get('campaign_id', '').strip()
        impact = mgr.cancel_campaign(cid)
        msg = f"Campanha cancelada. {impact.message}" if impact else "Campanha cancelada."
        return urlencode({'campaign_id': cid, 'msg': msg})

    elif action == 'cancel_slide':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        impact = mgr.queue.cancel_slide(slide_id)
        return urlencode({'campaign_id': cid, 'msg': f"Slide cancelado. {impact.message}"})

    elif action == 'set_monitoring_mode':
        cid = data.get('campaign_id', '').strip()
        mode = data.get('monitoring_mode', 'supervised').strip()
        mgr.set_monitoring_mode(cid, mode)
        return urlencode({'campaign_id': cid, 'msg': f"Modo de monitoramento alterado para '{mode.upper()}'."})

    elif action == 'regenerate_slide':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        prompt = data.get('new_prompt', '').strip() or None
        engine = data.get('engine_override', '').strip() or None
        mgr.regenerate_slide(cid, slide_id, new_prompt=prompt, engine_override=engine)
        return urlencode({'campaign_id': cid, 'msg': 'Intervenção localizada: novo trabalho agendado apenas para o slide afetado.'})

    elif action == 'reconcile_job':
        cid = data.get('campaign_id', '').strip()
        job_id = data.get('job_id', '').strip()
        outcome = data.get('outcome', 'failed').strip()
        mgr.queue.reconcile_uncertain_job(job_id, outcome=outcome)
        return urlencode({'campaign_id': cid, 'msg': f"Resultado incerto reconciliado como '{outcome}'."})

    elif action == 'run_worker':
        cid = data.get('campaign_id', '').strip()
        processed = app.worker.run_all_pending()
        return urlencode({'campaign_id': cid, 'msg': f"{processed} trabalho(s) processado(s) pelo worker local."})

    raise ValueError(f"Ação desconhecida: {action}")


def render_campaigns_hub(app: Application, query: Dict[str, Any]) -> str:
    """Renderiza a página /conteudo com painel de aprovação (Seção 75) e editor de storyboard/pipeline."""
    mgr = app.campaigns
    cid = query.get('campaign_id', [''])[0].strip()

    html = []
    html.append('<p class="eyebrow">Campanhas e Storyboard</p><h1>Conteúdo</h1>')
    html.append('<p class="intro">Planejamento visual, storyboard, pipeline multi-engine e governança de aprovação com vinculação estrita de orçamento.</p>')

    # Mensagens e alertas
    if query.get('msg'):
        html.append(f'<p role="status" class="notice">{escape(query["msg"][0])}</p>')
    if query.get('error'):
        html.append(f'<p role="alert" class="notice warning">{escape(query["error"][0])}</p>')

    # Se selecionou campanha, exibe a tela completa de aprovação (Seção 75)
    if cid:
        camp = mgr.get_campaign(cid)
        if camp:
            html.append(render_approval_screen(app, camp))
            return '\n'.join(html)

    # Formulário para criar nova campanha
    html.append('''
    <div class="panel">
        <span class="tag">Novo Projeto</span>
        <h2>Criar Campanha</h2>
        <p>Inicie a campanha definindo o conceito e o modo de governança. O Creative Director estruturará o storyboard inicial.</p>
        <form method="post" action="/api/campaigns/create" class="form-grid">
            <div class="form-group">
                <label for="camp_title">Título da Campanha</label>
                <input id="camp_title" name="title" placeholder="Ex: Campanha Velas Aromáticas Outono Nórdico" required>
            </div>
            <div class="form-group">
                <label for="camp_briefing">Conceito e Briefing Livre</label>
                <textarea id="camp_briefing" name="briefing_text" rows="3" placeholder="Descreva a ambientação, sensações e foco da campanha..." required></textarea>
            </div>
            <div class="form-group">
                <label for="camp_mode">Modo de Governança e Aprovação (Seção 56)</label>
                <select id="camp_mode" name="approval_mode">
                    <option value="minimal">Minimal — Aprovação conjunta do plano completo</option>
                    <option value="step_by_step">Step by Step — Aprovação progressiva etapa por etapa</option>
                    <option value="full_control">Full Control — Aprovação granular de cada slide e prompt</option>
                </select>
            </div>
            <button type="submit" class="button">Construir Campanha e Storyboard</button>
        </form>
    </div>
    ''')

    # Listagem de campanhas existentes
    campaigns = mgr.list_campaigns()
    if campaigns:
        html.append('''
        <div class="panel" style="margin-top:24px;">
            <span class="tag">Portfólio</span>
            <h2>Campanhas em Andamento</h2>
            <div class="provider-cards">
        ''')
        for c in campaigns:
            c_id = escape(c['id'])
            c_title = escape(c['title'])
            c_status = escape(c['status'].upper())
            c_mode = escape(c['approval_mode'])
            c_version = c['plan_version']
            c_slides = c['slides_count']
            c_cost = c['estimated_cost']

            badge_class = 'badge-success' if c['status'] == 'approved' else ('badge-error' if c['status'] in ('cancelled', 'failed') else 'status-active')

            html.append(f'''
            <div class="provider-card">
                <div class="card-header">
                    <div>
                        <span class="tag">v{c_version} · Modo: {c_mode}</span>
                        <h3>{c_title}</h3>
                    </div>
                    <span class="badge {badge_class}">{c_status}</span>
                </div>
                <p><strong>Slides:</strong> {c_slides} | <strong>Custo Estimado:</strong> R$ {c_cost:.2f}</p>
                <div class="card-actions">
                    <a href="/conteudo?campaign_id={c_id}" class="button" style="padding:8px 14px;font-size:13px;text-decoration:none;">Abrir Tela de Aprovação e Storyboard</a>
                </div>
            </div>
            ''')
        html.append('</div></div>')

    return '\n'.join(html)


def render_approval_screen(app: Application, camp: Any) -> str:
    """Renderiza a Tela de Aprovação rigorosa conforme Seção 75 da especificação."""
    mgr = app.campaigns
    data = mgr.get_approval_screen_data(camp.id)

    cid = escape(data['campaign_id'])
    title = escape(data['title'])
    obj = escape(data['objective'])
    sec_obj = escape(data['secondary_objective'])
    concept = escape(data['concept'])
    tone = escape(data['visual_tone'])
    generations = data['estimated_generations']
    cost = data['estimated_cost']
    conf = int(data['confidence'] * 100)
    status = escape(data['status'].upper())
    plan_ver = data['plan_version']
    is_approved = data['is_approved']
    mode = escape(data['approval_mode'])

    html = []
    html.append(f'''
    <div style="margin-bottom:18px;">
        <a href="/conteudo" class="button-secondary" style="display:inline-block;padding:8px 14px;font-size:12px;text-decoration:none;border-radius:3px;">← Voltar à lista de campanhas</a>
    </div>
    <div class="panel" role="region" aria-label="Tela de Aprovação">
        <div class="card-header">
            <div>
                <span class="tag">Tela de Aprovação · Seção 75</span>
                <h2>{title}</h2>
            </div>
            <div>
                <span class="tag">Versão do Plano: v{plan_ver}</span>
                <span class="badge {'badge-success' if is_approved else 'status-active'}">{status}</span>
            </div>
        </div>

        <div style="margin-top:16px;display:grid;gap:12px;font-size:14px;">
            <p><strong>Objetivo:</strong> <code>{obj}</code> (Secundário: <code>{sec_obj}</code>)</p>
            <p><strong>Conceito e Briefing:</strong> {concept}</p>
            <p><strong>Tom Visual:</strong> {tone}</p>
            <p><strong>Modo de Aprovação:</strong> <code>{mode}</code></p>
    ''')

    # Produtos selecionados
    prods = data['products']
    if prods:
        html.append('<p><strong>Produtos Selecionados:</strong></p><ul style="margin:0;padding-left:20px;">')
        for p in prods:
            html.append(f"<li><strong>{escape(p.get('name', 'Produto'))}</strong> ({escape(p.get('product_id', ''))})</li>")
        html.append('</ul>')

    # Resumo quantitativo de gerações e custos
    html.append(f'''
            <div style="background:var(--paper);padding:14px;border-radius:4px;margin-top:8px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
                <div><strong>Gerações Estimadas:</strong><br><span style="font-size:18px;font-family:var(--font-heading);">{generations}</span></div>
                <div><strong>Custo Estimado Total:</strong><br><span style="font-size:18px;font-family:var(--font-heading);">R$ {cost:.2f}</span></div>
                <div><strong>Nível de Confiança:</strong><br><span style="font-size:18px;font-family:var(--font-heading);">{conf}%</span></div>
            </div>
    ''')

    # Validação de aprovação vinculada
    if is_approved:
        appr_by = escape(data.get('approved_by') or 'Usuário')
        html.append(f'''
        <div class="notice" style="border-left:4px solid var(--ink);margin-top:12px;">
            <strong>✓ Plano v{plan_ver} Aprovado</strong> por <em>{appr_by}</em>.
            Orçamento reservado para execução.
        </div>
        ''')

    # Botões de Ação da Seção 75: [Editar] [Cancelar] [Aprovar execução]
    html.append('<div class="card-actions" style="margin-top:20px;">')
    c_stat_lower = camp.status.lower()
    if not is_approved:
        html.append(f'''
        <form method="post" action="/api/campaigns/approve" class="inline-form">
            <input type="hidden" name="campaign_id" value="{cid}">
            <input type="hidden" name="approver" value="Diretoria Criativa">
            <button type="submit" class="button" style="background:#273b32;margin-top:0;">Aprovar Execução (v{plan_ver})</button>
        </form>
        ''')
    elif c_stat_lower == 'approved':
        html.append(f'''
        <form method="post" action="/api/campaigns/queue" class="inline-form">
            <input type="hidden" name="campaign_id" value="{cid}">
            <button type="submit" class="button" style="background:#273b32;margin-top:0;">Enfileirar Execução na Fila</button>
        </form>
        ''')
    elif c_stat_lower in ('queued', 'running', 'paused', 'failed'):
        if c_stat_lower == 'paused':
            html.append(f'''
            <form method="post" action="/api/campaigns/resume" class="inline-form">
                <input type="hidden" name="campaign_id" value="{cid}">
                <button type="submit" class="button" style="background:#273b32;margin-top:0;">Retomar Execução</button>
            </form>
            ''')
        else:
            html.append(f'''
            <form method="post" action="/api/campaigns/pause" class="inline-form">
                <input type="hidden" name="campaign_id" value="{cid}">
                <button type="submit" class="button-secondary" style="margin-top:0;">Pausar Execução</button>
            </form>
            ''')
        html.append(f'''
        <form method="post" action="/api/campaigns/run_worker" class="inline-form">
            <input type="hidden" name="campaign_id" value="{cid}">
            <button type="submit" class="button" style="background:#273b32;margin-top:0;">Processar Fila (Worker Local)</button>
        </form>
        ''')

    html.append(f'''
        <form method="post" action="/api/campaigns/cancel" class="inline-form">
            <input type="hidden" name="campaign_id" value="{cid}">
            <button type="submit" class="button-danger" style="padding:12px 18px;">Cancelar Campanha</button>
        </form>
    </div></div>
    ''')

    # Seção: Fila de Execução e Monitoramento (Seções 50, 52, 67, 68, 69)
    jobs = mgr.list_jobs(camp.id)
    monitoring_mode = mgr.get_monitoring_mode(camp.id)
    impact = mgr.get_cancellation_impact(camp.id)

    if jobs or c_stat_lower in ('queued', 'running', 'paused', 'completed', 'failed'):
        html.append(f'''
        <div class="panel" style="margin-top:24px;">
            <div class="card-header">
                <div>
                    <span class="tag">Fila e Execução · Seções 50, 52, 67, 68, 69</span>
                    <h2>Monitoramento da Geração ({c_stat_lower.upper()})</h2>
                </div>
                <span class="badge {'badge-success' if c_stat_lower == 'completed' else 'status-active'}">{c_stat_lower.upper()}</span>
            </div>

            <!-- Seção 50: Modos de Acompanhamento Quick / Supervised / Detailed / Manual -->
            <div style="margin-top:14px;background:var(--paper);padding:14px;border-radius:4px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
                <div>
                    <strong>Modo de Monitoramento:</strong> <span class="tag">{monitoring_mode.upper()}</span>
                    <p class="hint" style="margin:4px 0 0 0;">Quick (automático direto), Supervised (acompanhado com alertas), Detailed (telemetria e logs), Manual (passo a passo).</p>
                </div>
                <form method="post" action="/api/campaigns/set_monitoring_mode" class="inline-form" style="margin:0;">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <select name="monitoring_mode" style="font-size:13px;padding:6px;">
                        <option value="supervised" {'selected' if monitoring_mode == 'supervised' else ''}>Supervised (Recomendado)</option>
                        <option value="quick" {'selected' if monitoring_mode == 'quick' else ''}>Quick (Rápido)</option>
                        <option value="detailed" {'selected' if monitoring_mode == 'detailed' else ''}>Detailed (Detalhado)</option>
                        <option value="manual" {'selected' if monitoring_mode == 'manual' else ''}>Manual (Passo a passo)</option>
                    </select>
                    <button type="submit" class="button-secondary" style="font-size:12px;padding:6px 12px;">Alterar Modo</button>
                </form>
            </div>
        ''')

        # Seção 52: Demonstrativo de custos, risco de cobrança e cancelamento
        if impact:
            html.append(f'''
            <div style="margin-top:14px;background:var(--paper);padding:14px;border-radius:4px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
                <div><strong>Custo Incorrido (Concluído):</strong><br><span style="font-size:18px;font-family:var(--font-heading);">R$ {impact.completed_cost:.2f}</span></div>
                <div><strong>Risco de Cobrança em Voo:</strong><br><span style="font-size:18px;font-family:var(--font-heading);color:#a84832;">R$ {impact.in_flight_risk:.2f}</span></div>
                <div><strong>Orçamento Poupado ao Cancelar:</strong><br><span style="font-size:18px;font-family:var(--font-heading);color:#273b32;">R$ {impact.cancellable_budget:.2f}</span></div>
            </div>
            ''')

        # Lista de Trabalhos na Fila e Diagnóstico de Falhas (Seção 67, 68, 69)
        if jobs:
            html.append('<div class="provider-cards" style="margin-top:16px;">')
            for job in jobs:
                j_id = escape(job.id)
                j_stat = escape(job.status.upper())
                j_prov = escape(job.provider_id.upper())
                j_mod = escape(job.model_id)
                j_cost = job.actual_cost if job.status == 'completed' else job.estimated_cost
                j_att = job.attempt
                j_max = job.max_retries

                html.append(f'''
                <div class="provider-card">
                    <div class="card-header">
                        <div>
                            <span class="tag">Trabalho · {j_prov}</span>
                            <h3>{escape(job.prompt[:40])}...</h3>
                        </div>
                        <span class="badge {'badge-success' if job.status == 'completed' else 'status-active'}">{j_stat}</span>
                    </div>
                    <p><strong>Modelo:</strong> <code>{j_mod}</code> | <strong>Tentativas:</strong> {j_att}/{j_max} | <strong>Custo:</strong> R$ {j_cost:.2f}</p>
                ''')

                # Seção 69: Card de Diagnóstico de Falha
                if job.status == 'failed' and job.diagnostic:
                    d = job.diagnostic
                    html.append(f'''
                    <div class="notice warning" style="margin-top:10px;border-left:4px solid #a84832;">
                        <strong>Diagnóstico de Falha (Seção 69):</strong><br>
                        <strong>Provedor:</strong> {escape(d.provider)} | <strong>Etapa:</strong> {escape(d.step)}<br>
                        <strong>Causa Provável:</strong> {escape(d.probable_cause)}<br>
                        <strong>Sugestão de Correção:</strong> {escape(d.suggested_fix)}<br>
                        <strong>Custo Potencial:</strong> R$ {d.potential_cost:.2f}
                    </div>
                    ''')

                # Seção 68: Reconciliação de Resultado Incerto
                if job.status == 'uncertain':
                    html.append(f'''
                    <div class="notice warning" style="margin-top:10px;border-left:4px solid #d48806;">
                        <strong>Resultado Incerto (Seção 68):</strong> Tempo limite atingido. Requisição não foi cobrada novamente.<br>
                        <form method="post" action="/api/campaigns/reconcile_job" class="inline-form" style="margin-top:8px;">
                            <input type="hidden" name="campaign_id" value="{cid}">
                            <input type="hidden" name="job_id" value="{j_id}">
                            <input type="hidden" name="outcome" value="success">
                            <button type="submit" class="button-secondary" style="font-size:12px;padding:4px 10px;">Confirmar Sucesso</button>
                        </form>
                        <form method="post" action="/api/campaigns/reconcile_job" class="inline-form" style="margin-top:8px;">
                            <input type="hidden" name="campaign_id" value="{cid}">
                            <input type="hidden" name="job_id" value="{j_id}">
                            <input type="hidden" name="outcome" value="failed">
                            <button type="submit" class="button-danger" style="font-size:12px;padding:4px 10px;">Confirmar Falha Sem Cobrança</button>
                        </form>
                    </div>
                    ''')

                html.append('</div>')
            html.append('</div>')

        html.append('</div>')

    # Seção: Storyboard (Slides)
    html.append(f'''
    <div class="panel" style="margin-top:24px;">
        <span class="tag">Storyboard · Visualização por Slide</span>
        <h2>Storyboard da Campanha ({len(data['storyboard'])} slides)</h2>
        <div class="idea-cards" style="margin-top:16px;">
    ''')
    for s in data['storyboard']:
        s_id = escape(s['id'])
        s_ord = s['slide_order']
        s_title = escape(s['title'])
        s_prompt = escape(s['visual_prompt'])
        s_frame = escape(s['framing'])
        s_caption = escape(s['caption_draft'])
        s_engine = escape(s.get('engine_override') or 'Padrão da campanha')

        # Versões preservadas do slide (Seção 52)
        slide_versions = mgr.list_slide_versions(s['id'])

        html.append(f'''
        <div class="card idea-card">
            <div class="card-header">
                <div>
                    <span class="tag">Slide {s_ord} · Enquadramento: {s_frame.upper()}</span>
                    <h3>{s_title}</h3>
                </div>
                <span class="badge status-active">{s_engine}</span>
            </div>
            <p><strong>Prompt Visual:</strong> <code>{s_prompt}</code></p>
            { f"<p><strong>Legenda Preliminar:</strong> <em>{s_caption}</em></p>" if s_caption else "" }
        ''')

        # Seção 52: Versões de imagem preservadas
        if slide_versions:
            html.append('<div style="background:var(--paper);padding:8px 12px;border-radius:4px;margin-top:8px;font-size:13px;"><strong>Versões Preservadas:</strong><ul style="margin:4px 0 0 0;padding-left:18px;">')
            for v in slide_versions:
                html.append(f"<li>v{v.version_number}: <code>{escape(v.asset_id or 'gerando')}</code> (R$ {v.actual_cost:.2f}) · {escape(v.provider_id.upper())}</li>")
            html.append('</ul></div>')

        # Seção 51: Intervenção localizada / Regenerar somente este slide
        html.append(f'''
            <details style="margin-top:10px;">
                <summary style="font-size:13px;padding:4px 0;">Intervenção Localizada · Regenerar ou alterar engine</summary>
                <form method="post" action="/api/campaigns/regenerate_slide" class="form-grid" style="margin-top:8px;">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <input type="hidden" name="slide_id" value="{s_id}">
                    <div class="form-group">
                        <label>Novo Prompt (ou manter atual)</label>
                        <textarea name="new_prompt" rows="2">{s_prompt}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Motor</label>
                        <select name="engine_override" style="font-size:13px;padding:6px;">
                            <option value="gemini:imagen-3.0-generate-002">Google Gemini Imagen 3</option>
                            <option value="gemini:imagen-3.0-fast-generate-001">Google Gemini Imagen 3 Fast</option>
                            <option value="openai:dall-e-3">OpenAI DALL-E 3</option>
                            <option value="adobe:firefly-image-3">Adobe Firefly 3</option>
                        </select>
                    </div>
                    <button type="submit" class="button-secondary" style="font-size:12px;padding:6px 12px;">Regenerar Somente Este Slide</button>
                </form>
            </details>
        </div>
        ''')

    # Formulário para adicionar mais um slide
    html.append(f'''
        <details class="revision" style="margin-top:16px;">
            <summary>+ Adicionar Slide ao Storyboard</summary>
            <form method="post" action="/api/campaigns/add_slide" class="form-grid" style="margin-top:12px;">
                <input type="hidden" name="campaign_id" value="{cid}">
                <div class="form-group">
                    <label>Título do Slide</label>
                    <input name="title" placeholder="Ex: Detalhe do Frasco com Chama Acesa" required>
                </div>
                <div class="form-group">
                    <label>Prompt Visual Detalhado</label>
                    <textarea name="visual_prompt" rows="2" placeholder="Descreva a composição, luz, materiais e ambiente..." required></textarea>
                </div>
                <div class="form-group">
                    <label>Enquadramento</label>
                    <select name="framing">
                        <option value="wide">Wide (Plano Aberto)</option>
                        <option value="medium" selected>Medium (Plano Médio)</option>
                        <option value="detail">Detail (Detalhe / Macro)</option>
                        <option value="close-up">Close-up</option>
                        <option value="overhead">Overhead (Vista Superior)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Rascunho de Legenda</label>
                    <input name="caption_draft" placeholder="Texto de apoio para o slide">
                </div>
                <button type="submit" class="button">Adicionar Slide</button>
            </form>
        </details>
    </div></div>
    ''')

    # Seção: Pipeline Multi-Engine e Edição Localizada (Seção 23 e 31)
    html.append(f'''
    <div class="panel" style="margin-top:24px;">
        <span class="tag">Pipeline Multi-Engine · Seções 23 e 31</span>
        <h2>Pipeline de Execução ({len(data['pipeline'])} etapas)</h2>
        <p class="hint">Usando o menor número de etapas necessário para máxima qualidade. Edições localizadas preservam etapas não afetadas.</p>
        <div class="provider-cards" style="margin-top:14px;">
    ''')
    for step in data['pipeline']:
        st_id = escape(step['id'])
        st_ord = step['step_order']
        st_name = escape(step['name'])
        st_prov = escape(step['provider_id'].upper())
        st_mod = escape(step['model_id'])
        st_cost = step['estimated_cost']
        st_stat = escape(step['status'].upper())

        html.append(f'''
        <div class="provider-card">
            <div class="card-header">
                <div>
                    <span class="tag">Etapa {st_ord} · {st_prov}</span>
                    <h3>{st_name}</h3>
                </div>
                <span class="badge status-active">{st_stat}</span>
            </div>
            <p><strong>Modelo:</strong> <code>{st_mod}</code> | <strong>Custo Estimado:</strong> R$ {st_cost:.2f}</p>
            <details style="margin-top:10px;">
                <summary style="font-size:13px;padding:4px 0;">Editar etapa localmente</summary>
                <form method="post" action="/api/campaigns/update_step" class="form-grid" style="margin-top:10px;">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <input type="hidden" name="step_id" value="{st_id}">
                    <div class="form-group">
                        <label>Nome da Etapa</label>
                        <input name="name" value="{st_name}" required>
                    </div>
                    <div class="form-group">
                        <label>Provedor</label>
                        <select name="provider_id">
                            <option value="gemini" {'selected' if 'gemini' in st_prov.lower() else ''}>Google Gemini</option>
                            <option value="openai" {'selected' if 'openai' in st_prov.lower() else ''}>OpenAI</option>
                            <option value="firefly" {'selected' if 'firefly' in st_prov.lower() else ''}>Adobe Firefly</option>
                            <option value="custom" {'selected' if 'custom' in st_prov.lower() else ''}>Custom</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Identificador do Modelo</label>
                        <input name="model_id" value="{st_mod}" required>
                    </div>
                    <button type="submit" class="button-secondary" style="font-size:12px;padding:8px 14px;">Salvar Alteração Localizada</button>
                </form>
            </details>
        ''')
        if mode in ('step_by_step', 'full_control') and step['status'] != 'approved':
            html.append(f'''
            <form method="post" action="/api/campaigns/approve_step" class="inline-form" style="margin-top:10px;">
                <input type="hidden" name="campaign_id" value="{cid}">
                <input type="hidden" name="step_id" value="{st_id}">
                <button type="submit" class="button-secondary" style="font-size:12px;padding:6px 12px;">Aprovar esta Etapa Individualmente</button>
            </form>
            ''')
        html.append('</div>')
    html.append('</div></div>')

    return '\n'.join(html)

