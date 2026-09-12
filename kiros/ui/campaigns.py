"""Interface de Campanhas, Storyboard, Pipeline e Tela de Aprovação (Seções 10, 23, 31, 56, 66, 75)."""
from datetime import datetime, timedelta, timezone
from html import escape
import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from kiros.application import Application
from kiros.campaigns.models import UnapprovedExecutionError
from kiros.core.contracts import Provenance
from kiros.layout import VALID_LAYOUT_FAMILIES, VALID_FRAMINGS, VALID_LIGHTINGS


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

    elif action == 'update_text_inline':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        title = data.get('title', '').strip()
        caption = data.get('caption_draft', '').strip()

        import sqlite3
        with sqlite3.connect(app.database.path) as db:
            db.execute("UPDATE storyboard_slides SET title=?, caption_draft=? WHERE id=?", (title, caption, slide_id))
        return urlencode({'campaign_id': cid, 'msg': '✨ Texto do slide atualizado com sucesso na prévia!'})

    elif action == 'approve_and_schedule_auto':
        cid = data.get('campaign_id', '').strip()
        approver = data.get('approver', 'Diretoria Criativa').strip()
        mgr.approve_campaign(cid, approver=approver)
        try:
            mgr.queue_execution(cid)
        except Exception:
            pass

        # Cria agendamento automático para amanhã no melhor horário (18:00)
        camp = mgr.get_campaign(cid)
        c_title = getattr(camp, 'title', 'Campanha KIROS')
        target_iso = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=18, minute=0, second=0).isoformat()
        app.calendar.create_entry(title=c_title, content_type='feed', pillar='institucional', scheduled_for=target_iso, campaign_id=cid, status='scheduled')

        return urlencode({'campaign_id': cid, 'msg': f'⚡ Campanha aprovada e agendada automaticamente para {target_iso[:10]} às 18:00 no Instagram (@usekiros)!'})

    elif action == 'approve_and_schedule_manual':
        cid = data.get('campaign_id', '').strip()
        approver = data.get('approver', 'Diretoria Criativa').strip()
        target_date = data.get('scheduled_date', '').strip()
        if not target_date:
            target_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%dT18:00:00+00:00')
        else:
            try:
                dt = datetime.fromisoformat(target_date.replace(' ', 'T'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                target_date = dt.isoformat()
            except Exception:
                target_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%dT18:00:00+00:00')

        mgr.approve_campaign(cid, approver=approver)
        try:
            mgr.queue_execution(cid)
        except Exception:
            pass

        camp = mgr.get_campaign(cid)
        c_title = getattr(camp, 'title', 'Campanha KIROS')
        app.calendar.create_entry(title=c_title, content_type='feed', pillar='institucional', scheduled_for=target_date, campaign_id=cid, status='scheduled')

        return urlencode({'campaign_id': cid, 'msg': f'📅 Campanha aprovada e agendada para {target_date}!'})


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

    elif action == 'choose_version':
        cid = data.get('campaign_id', '').strip()
        vid = data.get('version_id', '').strip()
        ver = mgr.choose_slide_version(vid)
        return urlencode({'campaign_id': cid, 'msg': f"Versão v{ver.version_number} definida como ativa para o slide."})

    elif action == 'restore_version':
        cid = data.get('campaign_id', '').strip()
        vid = data.get('version_id', '').strip()
        ver = mgr.restore_slide_version(vid)
        return urlencode({'campaign_id': cid, 'msg': f"Versão v{ver.version_number} restaurada sem apagar histórico."})

    elif action == 'use_as_base':
        cid = data.get('campaign_id', '').strip()
        vid = data.get('version_id', '').strip()
        new_prompt = data.get('new_prompt', '').strip() or None
        job = mgr.use_version_as_base(vid, new_prompt=new_prompt)
        return urlencode({'campaign_id': cid, 'msg': 'Nova geração baseada na versão selecionada agendada com prioridade.'})

    elif action == 'record_learning':
        cid = data.get('campaign_id', '').strip()
        vid = data.get('version_id', '').strip()
        note = data.get('learning_note', '').strip()
        mgr.record_version_learning(vid, note)
        return urlencode({'campaign_id': cid, 'msg': 'Aprendizado registrado na memória criativa e histórico permanente.'})

    elif action == 'set_fidelity_config':
        cid = data.get('campaign_id', '').strip()
        mode = data.get('fidelity_mode', 'recommend_before_spend').strip()
        threshold = float(data.get('fidelity_threshold', 85.0))
        app.fidelity_service.set_campaign_fidelity_config(cid, mode=mode, threshold=threshold)
        return urlencode({'campaign_id': cid, 'msg': f"Configuração de fidelidade atualizada: {mode} (Threshold: {threshold:.0f}/100)."})

    elif action == 'approve_fidelity_correction':
        cid = data.get('campaign_id', '').strip()
        check_id = data.get('check_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        res = app.fidelity_service.approve_correction(check_id)
        if slide_id and res.get('suggested_fix'):
            mgr.regenerate_slide(cid, slide_id, new_prompt=res['suggested_fix'])
        return urlencode({'campaign_id': cid, 'msg': 'Correção de fidelidade aprovada e regeneração do slide disparada.'})

    elif action == 'update_layout':
        cid = data.get('campaign_id', '').strip()
        lid = data.get('layout_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        confirm_protected = data.get('confirm_protected', '').strip() in ('1', 'true', 'on')
        unlock_critical = data.get('unlock_critical', '').strip() in ('1', 'true', 'on')
        audit_reason = data.get('audit_reason', '').strip() or None
        unlocked_by = data.get('unlocked_by', '').strip() or None

        updates = {}
        for k in (
            'position_x', 'position_y', 'scale', 'framing', 'lighting',
            'headline_text', 'cta_text', 'font_family', 'font_size',
            'headline_color', 'cta_color', 'decorative_kind', 'decorative_label',
            'logo_locked', 'logo_aspect_ratio',
        ):
            if k in data and data[k].strip() != '':
                updates[k] = data[k].strip()

        if 'logo_locked' in data:
            updates['logo_locked'] = data['logo_locked'].strip() in ('1', 'true', 'on')

        layout, msgs = mgr.update_slide_layout(
            layout_id=lid,
            updates=updates,
            confirm_protected=confirm_protected,
            unlock_critical=unlock_critical,
            audit_reason=audit_reason,
            unlocked_by=unlocked_by,
        )
        msg_text = 'Layout atualizado com sucesso. ' + ' '.join(msgs)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': msg_text.strip()})

    elif action == 'switch_layout_format':
        cid = data.get('campaign_id', '').strip()
        lid = data.get('layout_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        target_fmt = data.get('target_format', '4:5').strip()
        mgr.switch_slide_layout_format(lid, target_fmt)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': f"Formato alterado para '{target_fmt}' com adaptação responsiva determinística."})

    elif action == 'apply_template':
        cid = data.get('campaign_id', '').strip()
        lid = data.get('layout_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        template_id = data.get('template_id', '').strip()
        experimental_auth = data.get('experimental_authorized', '').strip() in ('1', 'true', 'on')
        mgr.apply_template_to_slide(lid, template_id, experimental_authorized=experimental_auth)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': 'Template de layout aplicado com sucesso.'})

    elif action == 'save_layout_as_template':
        cid = data.get('campaign_id', '').strip()
        lid = data.get('layout_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        name = data.get('template_name', '').strip()
        family = data.get('template_family', 'editorial_minimalist').strip()
        status = data.get('template_status', 'active').strip()
        tpl = mgr.save_slide_layout_as_template(lid, name=name, family=family, status=status)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': f"Composição salva como novo template '{tpl.name}' ({tpl.status})."})

    elif action == 'approve_layout':
        cid = data.get('campaign_id', '').strip()
        lid = data.get('layout_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        approver = data.get('approver', 'Diretoria de Arte').strip()
        app.layout_editor.approve_layout(lid, approved_by=approver)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': f"Composição de layout aprovada por {approver}."})

    elif action == 'update_slide_copy':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        mode = data.get('mode', 'automatic').strip()
        text = data.get('text', '').strip()
        user_draft = data.get('user_draft', '').strip()
        cta_mode = data.get('cta_mode', 'none').strip()
        cta_text = data.get('cta_text', '').strip()
        cta_intent = data.get('cta_intent', '').strip() or None
        destination_url = data.get('destination_url', '').strip()
        show_price = data.get('show_price', '').strip() in ('1', 'true', 'on')
        price_justification = data.get('price_justification', '').strip() or None
        price_approved_by = data.get('price_approved_by', '').strip() or None

        mgr.update_slide_copy(
            slide_id=slide_id,
            mode=mode,
            text=text if text else None,
            user_draft=user_draft,
            cta_mode=cta_mode,
            cta_text=cta_text,
            cta_intent=cta_intent,
            destination_url=destination_url,
            show_price=show_price,
            price_justification=price_justification,
            price_approved_by=price_approved_by,
        )
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': 'Copy e legenda atualizadas com governança de voz e preço.'})

    elif action == 'suggest_captions':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        mgr.generate_caption_suggestions_for_slide(slide_id)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': '3 novas opções de legenda geradas (Sensorial, Rotina, Minimalista).'})

    elif action == 'approve_price_display':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        justification = data.get('price_justification', '').strip()
        approver = data.get('price_approved_by', 'Diretoria Comercial').strip()
        mgr.approve_price_display(slide_id, justification=justification, approver=approver)
        return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': f'Exibição de preço aprovada com sucesso por {approver}.'})

    elif action == 'create_story_sequence':
        cid = data.get('campaign_id', '').strip()
        title = data.get('title', 'Sequência de Stories').strip()
        stype = data.get('story_type', 'derived_from_campaign').strip()
        obj = data.get('objective', '').strip()
        seq = mgr.create_story_sequence(title=title, story_type=stype, objective=obj, campaign_id=cid)
        return urlencode({'campaign_id': cid, 'msg': f"Sequência de Stories '{seq.title}' planejada com {len(seq.frames)} frames narrativos próprios."})

    elif action == 'add_story_frame':
        cid = data.get('campaign_id', '').strip()
        seq_id = data.get('sequence_id', '').strip()
        role = data.get('narrative_role', 'context').strip()
        title = data.get('title', '').strip()
        overlay = data.get('overlay_text', '').strip()
        prompt = data.get('visual_prompt', '').strip()
        itype = data.get('interaction_type', 'none').strip()
        ijust = data.get('interaction_justification', '').strip()
        caption = data.get('caption_draft', '').strip()
        mgr.add_story_frame(
            sequence_id=seq_id,
            narrative_role=role,
            title=title,
            overlay_text=overlay,
            visual_prompt=prompt,
            interaction_type=itype,
            interaction_justification=ijust,
            caption_draft=caption,
        )
        return urlencode({'campaign_id': cid, 'msg': 'Frame adicionado à sequência de Stories.'})

    elif action == 'audit_pre_publish':
        cid = data.get('campaign_id', '').strip()
        slide_id = data.get('slide_id', '').strip()
        seq_id = data.get('sequence_id', '').strip()
        if slide_id:
            res = mgr.audit_slide_pre_publish(slide_id)
            status_msg = "Aprovado para publicação!" if res.is_ready else f"Bloqueado na auditoria ({len(res.blocked_reasons)} pendências)."
            return urlencode({'campaign_id': cid, 'editor_slide_id': slide_id, 'msg': f"Auditoria do slide: {status_msg}"})
        elif seq_id:
            res = mgr.audit_story_sequence_pre_publish(seq_id)
            status_msg = "Aprovado para publicação!" if res.is_ready else f"Bloqueado na auditoria ({len(res.blocked_reasons)} pendências)."
            return urlencode({'campaign_id': cid, 'msg': f"Auditoria dos Stories: {status_msg}"})
        else:
            res = mgr.audit_campaign_pre_publish(cid)
            status_msg = "Campanha aprovada para publicação!" if res['is_ready'] else f"Campanha possui itens bloqueados ({len(res['blocked_reasons'])} pendências)."
            return urlencode({'campaign_id': cid, 'msg': f"Auditoria geral da campanha: {status_msg}"})

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
            html.append(render_approval_screen(app, camp, query=query))
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


def render_approval_screen(app: Application, camp: Any, query: Optional[Dict[str, Any]] = None) -> str:
    """Renderiza a Tela de Aprovação rigorosa conforme Seção 75 da especificação."""
    mgr = app.campaigns
    data = mgr.get_approval_screen_data(camp.id)
    fidelity_cfg = app.fidelity_service.get_campaign_fidelity_config(camp.id)

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
    ''')

    # Seção 54: Painel de Comparação Visual Lado a Lado (até 3 versões)
    compare_vids = []
    if query:
        raw_vids = query.get('compare_versions', [])
        for item in raw_vids:
            for v in item.split(','):
                clean_v = v.strip()
                if clean_v and clean_v not in compare_vids:
                    compare_vids.append(clean_v)

    if compare_vids:
        try:
            comp = mgr.compare_slide_versions(compare_vids[:3])
            c_versions = comp['versions']
            c_diffs = comp['differences']
            html.append(f'''
            <div class="panel" style="margin-bottom:24px;border:2px solid var(--accent);background:#fcfbf9;">
                <div class="card-header">
                    <div>
                        <span class="tag">Comparação Visual · Seção 54</span>
                        <h2>Comparação Lado a Lado ({len(c_versions)} versões de até 3)</h2>
                    </div>
                    <a href="/conteudo?campaign_id={cid}" class="button-secondary" style="font-size:12px;padding:6px 12px;text-decoration:none;">✕ Fechar Comparação</a>
                </div>
                <p class="hint" style="margin-top:4px;">Exibindo imagem, engine, modelo, custo, fidelidade e diferenças conforme Seção 54.</p>
                <div style="display:grid;grid-template-columns:repeat({len(c_versions)},1fr);gap:16px;margin-top:14px;">
            ''')
            for ver in c_versions:
                v_id = escape(ver['id'])
                v_num = ver['version_number']
                v_eng = escape(f"{ver['provider_id'].upper()} · {ver['model_id']}")
                v_cost = ver['actual_cost']
                v_fid = ver['fidelity_score']
                fid_text = f"Fidelidade: {v_fid:.0f}/100" if v_fid is not None else "Fidelidade: Pendente"
                fid_badge_style = "background:#e6f4ea;color:#137333;" if (v_fid is not None and v_fid >= 85) else "background:#fef7e0;color:#b06000;"
                v_asset = escape(ver['asset_id'] or 'em processamento')
                v_prompt = escape(ver['prompt'])
                is_cur = ver.get('is_current', False)

                html.append(f'''
                <div class="card" style="background:#fff;border:{'2px solid #273b32' if is_cur else '1px solid var(--border)'};padding:14px;border-radius:4px;">
                    <div class="card-header" style="margin-bottom:8px;">
                        <div>
                            <strong style="font-size:16px;">v{v_num}</strong>
                            {'<span class="badge status-active" style="background:#273b32;color:#fff;margin-left:6px;">ATIVA</span>' if is_cur else ''}
                        </div>
                        <span class="tag">R$ {v_cost:.2f}</span>
                    </div>
                    <div style="height:110px;background:#f0ede8;display:flex;align-items:center;justify-content:center;border-radius:4px;margin-bottom:8px;">
                        <code style="font-size:11px;">{v_asset}</code>
                    </div>
                    <p style="font-size:12px;margin:3px 0;"><strong>Engine:</strong> {v_eng}</p>
                    <p style="font-size:12px;margin:3px 0;"><span class="badge" style="{fid_badge_style}">{fid_text}</span> <span class="hint" style="font-size:10px;">(estimativa)</span></p>
                    <p style="font-size:11px;margin:3px 0;"><strong>Motivo:</strong> {escape(ver.get('reason', 'Geração inicial'))}</p>
                    <p style="font-size:11px;color:var(--muted);max-height:45px;overflow:hidden;margin-top:6px;">{v_prompt[:130]}...</p>

                    <!-- Ações da Seção 54: choose, use_as_base, record_learning -->
                    <div style="margin-top:12px;display:flex;flex-direction:column;gap:6px;">
                        <form method="post" action="/api/campaigns/choose_version" style="margin:0;">
                            <input type="hidden" name="campaign_id" value="{cid}">
                            <input type="hidden" name="version_id" value="{v_id}">
                            <button type="submit" class="button-secondary" style="width:100%;font-size:11px;padding:6px;">Escolher como Ativa (choose)</button>
                        </form>
                        <form method="post" action="/api/campaigns/use_as_base" style="margin:0;">
                            <input type="hidden" name="campaign_id" value="{cid}">
                            <input type="hidden" name="version_id" value="{v_id}">
                            <button type="submit" class="button-secondary" style="width:100%;font-size:11px;padding:6px;">Usar como Base (use_as_base)</button>
                        </form>
                        <details style="font-size:11px;margin-top:2px;">
                            <summary style="padding:4px 0;cursor:pointer;">Registrar Aprendizado (record_learning)</summary>
                            <form method="post" action="/api/campaigns/record_learning" style="margin-top:6px;">
                                <input type="hidden" name="campaign_id" value="{cid}">
                                <input type="hidden" name="version_id" value="{v_id}">
                                <textarea name="learning_note" rows="2" placeholder="O que funcionou ou divergiu nesta versão..." style="font-size:11px;width:100%;box-sizing:border-box;" required></textarea>
                                <button type="submit" class="button-secondary" style="margin-top:4px;width:100%;font-size:11px;padding:4px;">Salvar Aprendizado</button>
                            </form>
                        </details>
                    </div>
                </div>
                ''')

            html.append(f'''
                </div>
                <!-- Resumo das Diferenças da Seção 54 -->
                <div style="margin-top:14px;background:#fff;padding:12px;border-radius:4px;font-size:12px;border:1px solid var(--border);">
                    <strong>Diferenças Detectadas na Comparação:</strong>
                    <ul style="margin:4px 0 0 0;padding-left:18px;">
                        <li><strong>Motores:</strong> {'Diferentes entre as versões' if c_diffs['engines_differ'] else 'Idênticos'} ({", ".join(c_diffs['engines'])})</li>
                        <li><strong>Variação de Custo:</strong> R$ {c_diffs['cost_diff']:.2f} (Mín: R$ {c_diffs['cost_min']:.2f} / Máx: R$ {c_diffs['cost_max']:.2f})</li>
                        <li><strong>Prompts:</strong> {'Modificados entre as versões' if c_diffs['prompts_differ'] else 'Idênticos'}</li>
                        <li><strong>Fidelidade:</strong> {'Variação nos scores de fidelidade' if c_diffs['fidelities_differ'] else 'Scores compatíveis'}</li>
                    </ul>
                </div>
            </div>
            ''')
        except Exception as e:
            html.append(f'<p class="notice warning">Erro ao carregar comparação de versões: {escape(str(e))}</p>')

    html.append(f'''
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
        <div class="notice" style="border:1px solid var(--hairline);background:var(--surface-input);margin-top:12px;">
            <strong>✓ Plano v{plan_ver} Aprovado</strong> por <em>{appr_by}</em>.
            Orçamento reservado para execução.
        </div>
        ''')

    # Botoeira Dupla de Aprovação e Agendamento no Instagram (@usekiros)
    html.append('<div class="card-actions" style="margin-top:20px; display:flex; gap:12px; flex-wrap:wrap;">')
    c_stat_lower = camp.status.lower()
    if not is_approved:
        html.append(f'''
        <form method="post" action="/api/campaigns/approve_and_schedule_auto" class="inline-form" style="flex:1;">
            <input type="hidden" name="campaign_id" value="{cid}">
            <input type="hidden" name="approver" value="Diretoria Criativa">
            <button type="submit" class="button" style="background:#693edf; width:100%; text-align:center;">⚡ Aprovar &amp; Agendar Automático (Melhor Horário @usekiros)</button>
        </form>
        <form method="post" action="/api/campaigns/approve_and_schedule_manual" class="inline-form" style="flex:1; display:flex; gap:6px;">
            <input type="hidden" name="campaign_id" value="{cid}">
            <input type="hidden" name="approver" value="Diretoria Criativa">
            <input type="datetime-local" name="scheduled_date" style="padding:6px; font-size:12px;" required>
            <button type="submit" class="button-secondary" style="white-space:nowrap;">📅 Agendar Data/Hora</button>
        </form>
        ''')
    elif c_stat_lower == 'approved':
        html.append(f'''
        <form method="post" action="/api/campaigns/queue" class="inline-form">
            <input type="hidden" name="campaign_id" value="{cid}">
            <button type="submit" class="button" style="background:#273b32;margin-top:0;">Enfileirar Execução na Fila do Instagram</button>
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

            <!-- Seção 27: Configuração de Fidelidade de Produto (warn_only, auto_regenerate, recommend_before_spend) -->
            <div style="margin-top:10px;background:var(--paper);padding:14px;border-radius:4px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
                <div>
                    <strong>Fidelidade de Produto (Seção 27):</strong> <span class="tag">{fidelity_cfg['mode'].upper()}</span> · Threshold: <strong>{fidelity_cfg['threshold']:.0f}/100</strong>
                    <p class="hint" style="margin:4px 0 0 0;">recommend_before_spend (padrão: recomenda antes de gastar), warn_only (apenas alerta), auto_regenerate (sujeito a orçamento e tentativas).</p>
                </div>
                <form method="post" action="/api/campaigns/set_fidelity_config" class="inline-form" style="margin:0;display:flex;gap:8px;align-items:center;">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <select name="fidelity_mode" style="font-size:13px;padding:6px;">
                        <option value="recommend_before_spend" {'selected' if fidelity_cfg['mode'] == 'recommend_before_spend' else ''}>recommend_before_spend (Padrão)</option>
                        <option value="warn_only" {'selected' if fidelity_cfg['mode'] == 'warn_only' else ''}>warn_only (Apenas alertar)</option>
                        <option value="auto_regenerate" {'selected' if fidelity_cfg['mode'] == 'auto_regenerate' else ''}>auto_regenerate (Auto-regenerar)</option>
                    </select>
                    <input type="number" name="fidelity_threshold" value="{fidelity_cfg['threshold']:.0f}" min="50" max="100" style="width:70px;font-size:13px;padding:6px;" title="Threshold de fidelidade (0 a 100)">
                    <button type="submit" class="button-secondary" style="font-size:12px;padding:6px 12px;">Salvar Config</button>
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
                    <div class="notice warning" style="margin-top:10px;border:1px solid var(--hairline-cool);background:var(--surface-input);">
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
                    <div class="notice warning" style="margin-top:10px;border:1px solid var(--hairline-cool);background:var(--surface-input);">
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
        slide_layout = mgr.get_slide_layout(s['id'])
        is_editor_open = bool(query and query.get('editor_slide_id', [''])[0] == s['id'])

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

        # Seção 52 e 53: Versões de imagem preservadas com metadados e fidelidade
        if slide_versions:
            html.append('<div style="background:var(--paper);padding:10px 14px;border-radius:4px;margin-top:10px;font-size:13px;">')
            html.append('<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><strong>Versões Preservadas (Seção 53):</strong><span class="hint" style="font-size:11px;">Histórico permanente</span></div>')
            html.append(f'<form method="get" action="/conteudo" style="margin:0;">')
            html.append(f'<input type="hidden" name="campaign_id" value="{cid}">')
            html.append(f'<input type="hidden" name="compare_slide_id" value="{s_id}">')
            html.append('<div style="display:flex;flex-direction:column;gap:6px;margin:6px 0;">')
            for v in slide_versions:
                v_fid = v.fidelity_score
                fid_badge = f'<span class="badge" style="background:#e6f4ea;color:#137333;font-size:11px;">Fidelidade: {v_fid:.0f}/100</span>' if (v_fid is not None and v_fid >= 85) else (f'<span class="badge" style="background:#fef7e0;color:#b06000;font-size:11px;">Fidelidade: {v_fid:.0f}/100</span>' if v_fid is not None else '<span class="tag" style="font-size:11px;">Fidelidade: Pendente</span>')
                cur_badge = '<span class="badge status-active" style="background:#273b32;color:#fff;font-size:10px;padding:2px 6px;">Ativa</span>' if v.is_current else ''
                html.append(f'''
                <div style="display:flex;align-items:center;justify-content:space-between;background:#fff;padding:6px 10px;border-radius:3px;border:1px solid var(--border);flex-wrap:wrap;gap:6px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" name="compare_versions" value="{v.id}" title="Selecionar para comparar">
                        <strong>v{v.version_number}</strong>
                        <code>{escape(v.asset_id or 'gerando')}</code>
                        <span>(R$ {v.actual_cost:.2f})</span>
                        <span class="tag">{escape(v.provider_id.upper())}</span>
                        {cur_badge}
                        {fid_badge}
                    </div>
                    <div style="display:flex;gap:6px;">
                        <button type="submit" formaction="/api/campaigns/choose_version" formmethod="post" name="version_id" value="{v.id}" class="button-secondary" style="font-size:11px;padding:3px 8px;">Escolher</button>
                        <button type="submit" formaction="/api/campaigns/restore_version" formmethod="post" name="version_id" value="{v.id}" class="button-secondary" style="font-size:11px;padding:3px 8px;">Restaurar</button>
                    </div>
                </div>
                ''')
            html.append('</div>')
            html.append('<div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;flex-wrap:wrap;gap:8px;">')
            html.append('<button type="submit" class="button-secondary" style="font-size:11px;padding:5px 12px;">Comparar Selecionadas (Até 3) Lado a Lado</button>')
            html.append('<span class="hint" style="font-size:11px;">O score é uma estimativa de visão computacional, não uma prova absoluta.</span>')
            html.append('</div>')
            html.append('</form>')
            html.append('</div>')

        # Seção 27: Alerta estruturado de falha de fidelidade de produto
        slide_checks = app.fidelity_service.list_checks_for_slide(s['id'])
        for chk in slide_checks:
            if not chk.passed:
                html.append(f'''
                <div style="margin-top:10px;background:var(--surface-input);border:1px solid var(--hairline-cool);padding:12px;border-radius:var(--radius-sm);font-size:13px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <strong>⚠️ Alerta de Fidelidade de Produto ({chk.formatted_score})</strong>
                        <span class="tag">Threshold: {chk.threshold:.0f} · Modo: {chk.mode.upper()}</span>
                    </div>
                    <p style="margin:4px 0 2px 0;"><strong>Problema Detectado:</strong></p>
                    <ul style="margin:2px 0 6px 0;padding-left:18px;">
                ''')
                for d in chk.discrepancies:
                    html.append(f"<li><code>{escape(d.attribute)}</code> ({escape(d.severity)}): {escape(d.explanation)}</li>")
                html.append(f'''
                    </ul>
                    <p style="margin:4px 0;"><strong>Sugestão de Correção:</strong> {escape(chk.suggested_fix or '')}</p>
                    <p style="margin:4px 0;"><strong>Custo Estimado da Correção:</strong> R$ {chk.estimated_correction_cost:.2f}</p>
                ''')
                if chk.approval_status == 'pending':
                    html.append(f'''
                    <form method="post" action="/api/campaigns/approve_fidelity_correction" style="margin-top:8px;">
                        <input type="hidden" name="campaign_id" value="{cid}">
                        <input type="hidden" name="check_id" value="{chk.id}">
                        <input type="hidden" name="slide_id" value="{s_id}">
                        <button type="submit" class="button-primary" style="font-size:12px;padding:6px 12px;">Aprovar Correção e Regenerar Slide (R$ {chk.estimated_correction_cost:.2f})</button>
                    </form>
                    ''')
                elif chk.approval_status == 'auto_applied':
                    html.append('<span class="badge badge-success" style="margin-top:6px;display:inline-block;">Auto-regeneração disparada dentro do orçamento disponível</span>')
                html.append('</div>')

        # Seção 80: Aprendizados registrados para este slide
        slide_learnings = mgr.list_learnings_for_slide(s['id'])
        if slide_learnings:
            html.append('<div style="margin-top:8px;background:#f4f6f8;padding:8px 12px;border-radius:4px;font-size:12px;"><strong>Aprendizados Registrados (Seção 80):</strong><ul style="margin:4px 0 0 0;padding-left:18px;">')
            for l in slide_learnings:
                html.append(f"<li><em>{escape(l['learning_note'])}</em> <span class='hint'>({escape(l['created_at'][:19])})</span></li>")
            html.append('</ul></div>')


        # Edição Direta de Texto In-Line (Edite sem precisar recriar a campanha)
        html.append(f'''
            <details style="margin-top:10px;" open>
                <summary style="font-size:13px; font-weight:600; color:#4514a6; cursor:pointer;">✏️ Edição Direta de Texto do Slide (In-Line)</summary>
                <form method="post" action="/api/campaigns/update_text_inline" class="form-grid" style="margin-top:8px;">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <input type="hidden" name="slide_id" value="{s_id}">
                    <div class="form-group">
                        <label style="font-size:12px;">Título do Slide</label>
                        <input name="title" value="{s_title}" style="font-size:13px;" required>
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px;">Legenda / Copy do Slide</label>
                        <textarea name="caption_draft" rows="2" style="font-size:13px;" required>{s_caption}</textarea>
                    </div>
                    <button type="submit" class="button-secondary" style="font-size:12px; padding:6px 12px;">✨ Salvar Texto Direto na Prévia</button>
                </form>
            </details>

            <details style="margin-top:10px;">
                <summary style="font-size:13px;padding:4px 0;">🎨 Intervenção Localizada · Regenerar Somente Este Slide</summary>

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

            <!-- Seções 28, 29, 30: Layout Determinístico e Editor Visual Semântico -->
            <div style="margin-top:12px;padding:10px 14px;background:#f0ede8;border-radius:4px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <strong>Design &amp; Layout:</strong>
                    <span class="tag">Formato {slide_layout.format}</span>
                    <span class="badge {'badge-success' if slide_layout.is_approved else 'status-active'}">{'Aprovado' if slide_layout.is_approved else 'Rascunho'}</span>
                </div>
                <a href="/conteudo?campaign_id={cid}&editor_slide_id={s_id}" class="button" style="margin:0;padding:6px 12px;font-size:12px;text-decoration:none;background:#273b32;color:#fff;">🎨 {'Editor Aberto' if is_editor_open else 'Abrir Editor de Layout (4:5 / 9:16)'}</a>
            </div>

            { render_slide_layout_editor(app, cid, s, slide_layout, query) if is_editor_open else "" }

            <!-- Seções 34-37: Copy, Legenda e Auditoria Pré-Publicação do Slide -->
            { render_slide_copy_and_audit(app, cid, s, query) }
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

    # Seção 38: Planejador de Stories (Sequência Narrativa Própria)
    html.append(render_stories_planner(app, cid, query))

    # M08-A05: Auditoria Geral Pré-Publicação da Campanha
    html.append(render_campaign_pre_publish_card(app, cid, query))

    return '\n'.join(html)


def render_slide_layout_editor(app: Application, cid: str, s: Dict[str, Any], layout: Any, query: Optional[Dict[str, Any]] = None) -> str:
    """Renderiza o Editor Visual Semântico e Biblioteca de Templates (Seções 28, 29, 30)."""
    s_id = escape(s['id'])
    lid = escape(layout.id)
    fmt = layout.format
    w, h = app.layout_engine.get_dimensions(fmt)
    svg_preview = app.layout_engine.render_svg(layout, show_safe_areas=True)

    # Informações de template
    all_templates = app.template_library.list_templates()
    current_tpl = app.template_library.get_template(layout.template_id) if layout.template_id else None
    tpl_name = escape(current_tpl.name) if current_tpl else "Composição Livre"

    # Detecção de sobreuso se template ativo
    overuse_info = app.template_library.detect_overuse(layout.template_id) if layout.template_id else None

    # Histórico de auditoria de atributos críticos
    audit_logs = app.layout_editor.list_audit_entries(layout_id=layout.id)

    # Opções de enquadramento
    framing_options = ''.join(
        f'<option value="{f}" {"selected" if layout.image.framing == f else ""}>{f.capitalize()}</option>'
        for f in VALID_FRAMINGS
    )

    # Opções de iluminação
    lighting_options = ''.join(
        f'<option value="{li}" {"selected" if layout.image.lighting == li else ""}>{li.replace("_", " ").capitalize()}</option>'
        for li in VALID_LIGHTINGS
    )

    # Opções de famílias de layout
    family_options = ''.join(
        f'<option value="{fam}">{fam.replace("_", " ").capitalize()}</option>'
        for fam in VALID_LAYOUT_FAMILIES
    )

    # Templates para seleção
    tpl_options = ''.join(
        f'<option value="{t.id}" {"selected" if layout.template_id == t.id else ""}>{escape(t.name)} ({t.family} - {t.status})</option>'
        for t in all_templates
    )

    # Tabela de auditoria
    audit_html = ''
    if audit_logs:
        audit_rows = ''.join(
            f'<tr><td><code>{escape(a.attribute_name)}</code></td><td>{escape(a.previous_value)}</td><td><strong>{escape(a.new_value)}</strong></td><td><em>{escape(a.reason)}</em></td><td>{escape(a.operator)}</td><td>{escape(a.created_at[:19])}</td></tr>'
            for a in audit_logs
        )
        audit_html = f'''
        <div style="margin-top:16px;background:#fff;padding:12px;border:1px solid var(--line);border-radius:4px;">
            <strong style="color:#8a2e1d;">Registro de Exceções Auditadas (Seção 29):</strong>
            <div class="table-scroll" style="margin-top:6px;">
                <table style="font-size:11px;">
                    <thead><tr><th>Atributo</th><th>Anterior</th><th>Novo</th><th>Justificativa</th><th>Responsável</th><th>Data</th></tr></thead>
                    <tbody>{audit_rows}</tbody>
                </table>
            </div>
        </div>
        '''

    overuse_banner = ''
    if overuse_info and overuse_info['is_overused']:
        overuse_banner = f'''
        <div class="notice warning" style="margin-top:12px;border:1px solid var(--hairline-cool);background:var(--surface-input);">
            <strong>⚠️ Alerta de Sobreuso de Template (Seção 30 e 32):</strong><br>
            {escape(overuse_info['warning'])}
        </div>
        '''

    html = f'''
    <div class="panel" style="margin-top:16px;border:1px solid var(--hairline);background:var(--canvas);padding:20px;border-radius:var(--radius-sm);max-width:100%;">
        <div class="card-header" style="border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:16px;">
            <div>
                <span class="tag">Editor Visual Semântico · Seções 28, 29, 30</span>
                <h3 style="margin:4px 0 0 0;font-size:20px;">Design &amp; Layout Determinístico · {escape(s['title'])}</h3>
                <p class="hint" style="margin:2px 0 0 0;">Não delega texto exato, logo ou posicionamento ao gerador de imagens. Sem alucinações de LLM.</p>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <span class="badge" style="background:var(--surface-input);color:var(--ink);">Formato {fmt} ({w}×{h})</span>
                <a href="/conteudo?campaign_id={cid}" class="button-secondary" style="font-size:11px;padding:4px 8px;text-decoration:none;">Fechar Editor ✕</a>
            </div>
        </div>

        <!-- Seletor de Formato: 4:5 vs 9:16 -->
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;background:var(--paper);padding:10px 14px;border-radius:4px;flex-wrap:wrap;">
            <strong>Alternar Formato:</strong>
            <form method="post" action="/api/campaigns/switch_layout_format" style="margin:0;display:inline;">
                <input type="hidden" name="campaign_id" value="{cid}">
                <input type="hidden" name="layout_id" value="{lid}">
                <input type="hidden" name="slide_id" value="{s_id}">
                <input type="hidden" name="target_format" value="4:5">
                <button type="submit" class="{'button' if fmt == '4:5' else 'button-secondary'}" style="font-size:11px;padding:5px 12px;margin:0;">Feed 4:5 (1080×1350)</button>
            </form>
            <form method="post" action="/api/campaigns/switch_layout_format" style="margin:0;display:inline;">
                <input type="hidden" name="campaign_id" value="{cid}">
                <input type="hidden" name="layout_id" value="{lid}">
                <input type="hidden" name="slide_id" value="{s_id}">
                <input type="hidden" name="target_format" value="9:16">
                <button type="submit" class="{'button' if fmt == '9:16' else 'button-secondary'}" style="font-size:11px;padding:5px 12px;margin:0;">Stories 9:16 (1080×1920)</button>
            </form>
            <span class="hint" style="margin-left:auto;">Proporção {'0.80' if fmt == '4:5' else '0.5625'} matematicamente verificada.</span>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">
            <!-- Coluna Esquerda: Preview SVG e Exportação -->
            <div>
                <h4>Preview Determinístico ({fmt})</h4>
                <div style="max-width:320px;margin:0 auto;border:1px solid var(--line);border-radius:4px;overflow:hidden;box-shadow:0 4px 14px rgba(0,0,0,0.08);background:#f5efe6;">
                    {svg_preview}
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;justify-content:center;">
                    <a href="/api/layout/svg?layout_id={lid}" target="_blank" class="button-secondary" style="font-size:11px;padding:5px 10px;text-decoration:none;">Visualizar SVG ↗</a>
                    <a href="/api/layout/svg?layout_id={lid}&safe_areas=1" target="_blank" class="button-secondary" style="font-size:11px;padding:5px 10px;text-decoration:none;">Safe Areas 📐</a>
                    <a href="/api/layout/export?layout_id={lid}" target="_blank" class="button-secondary" style="font-size:11px;padding:5px 10px;text-decoration:none;">Dados JSON 📦</a>
                </div>

                <!-- Aprovação da Composição -->
                <div style="margin-top:18px;background:var(--paper);padding:12px;border-radius:4px;">
                    <strong>Aprovação Formal de Layout (Seção 30):</strong>
                    <form method="post" action="/api/campaigns/approve_layout" style="margin-top:8px;display:flex;gap:8px;align-items:center;">
                        <input type="hidden" name="campaign_id" value="{cid}">
                        <input type="hidden" name="layout_id" value="{lid}">
                        <input type="hidden" name="slide_id" value="{s_id}">
                        <input name="approver" value="{escape(layout.approved_by or 'Diretoria de Arte')}" style="font-size:12px;padding:6px;max-width:180px;" required>
                        <button type="submit" class="button" style="font-size:11px;padding:6px 12px;margin:0;">Aprovar Layout</button>
                    </form>
                    { f"<p class='hint' style='margin:4px 0 0 0;color:#137333;'>Aprovado por {escape(layout.approved_by)} em {escape(layout.approved_at[:19])}</p>" if layout.is_approved else "" }
                </div>

                <!-- Alerta de Sobreuso se houver -->
                {overuse_banner}

                <!-- Garantia de Isolamento da Product Bible -->
                <div style="margin-top:14px;padding:10px 14px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm);font-size:12px;">
                    <strong>🛡️ Garantia de Isolamento (M07-A03):</strong><br>
                    A edição de layout opera estritamente no nível da composição e nunca altera a Product Bible oficial automaticamente (Seção 29). Bloqueio validado no servidor.
                </div>
            </div>

            <!-- Coluna Direita: Controles Verde / Amarelo / Vermelho e Templates -->
            <div>
                <h4>Controles Semânticos de Layout (Seção 29)</h4>
                <form method="post" action="/api/campaigns/update_layout" style="margin-top:10px;">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <input type="hidden" name="layout_id" value="{lid}">
                    <input type="hidden" name="slide_id" value="{s_id}">

                    <!-- Painel Verde (Livre) -->
                    <div style="background:var(--surface-input);border:1px solid var(--hairline);padding:12px;border-radius:var(--radius-sm);margin-bottom:14px;">
                        <strong style="color:var(--ink);">🟢 Verde · Livre (Sem restrições)</strong>
                        <p class="hint" style="margin:2px 0 8px 0;">Posição, escala, enquadramento e iluminação podem ser alterados livremente.</p>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                            <div>
                                <label style="font-size:11px;">Enquadramento:</label>
                                <select name="framing" style="font-size:12px;padding:4px;">
                                    {framing_options}
                                </select>
                            </div>
                            <div>
                                <label style="font-size:11px;">Iluminação:</label>
                                <select name="lighting" style="font-size:12px;padding:4px;">
                                    {lighting_options}
                                </select>
                            </div>
                            <div>
                                <label style="font-size:11px;">Posição Imagem X:</label>
                                <input type="number" name="position_x" value="{layout.image.position_x}" style="font-size:12px;padding:4px;">
                            </div>
                            <div>
                                <label style="font-size:11px;">Posição Imagem Y:</label>
                                <input type="number" name="position_y" value="{layout.image.position_y}" style="font-size:12px;padding:4px;">
                            </div>
                            <div style="grid-column:span 2;">
                                <label style="font-size:11px;">Escala do Produto ({layout.image.scale:.2f}x):</label>
                                <input type="number" step="0.05" min="0.2" max="2.5" name="scale" value="{layout.image.scale}" style="font-size:12px;padding:4px;">
                            </div>
                        </div>
                    </div>

                    <!-- Painel Amarelo (Protected) -->
                    <div style="background:var(--surface-input);border:1px solid var(--hairline);padding:12px;border-radius:var(--radius-sm);margin-bottom:14px;">
                        <strong style="color:var(--ink);">🟡 Amarelo · Protected (Exige confirmação)</strong>
                        <p class="hint" style="margin:2px 0 8px 0;">Textos exatos, cores e tipografia exigem confirmação explícita.</p>
                        <div style="display:grid;gap:8px;">
                            <div>
                                <label style="font-size:11px;">Texto da Headline:</label>
                                <input name="headline_text" value="{escape(layout.headline.text)}" style="font-size:12px;padding:5px;" required>
                            </div>
                            <div>
                                <label style="font-size:11px;">Texto do CTA:</label>
                                <input name="cta_text" value="{escape(layout.cta.text)}" style="font-size:12px;padding:5px;" required>
                            </div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                <div>
                                    <label style="font-size:11px;">Tamanho da Fonte:</label>
                                    <input type="number" name="font_size" value="{layout.headline.font_size}" style="font-size:12px;padding:4px;">
                                </div>
                                <div>
                                    <label style="font-size:11px;">Cor da Headline:</label>
                                    <input name="headline_color" value="{escape(layout.headline.color)}" style="font-size:12px;padding:4px;">
                                </div>
                            </div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                <div>
                                    <label style="font-size:11px;">Elemento Decorativo:</label>
                                    <select name="decorative_kind" style="font-size:12px;padding:4px;">
                                        <option value="badge" {"selected" if layout.decorative.kind == 'badge' else ""}>Selo / Badge</option>
                                        <option value="divider" {"selected" if layout.decorative.kind == 'divider' else ""}>Linha Divisória</option>
                                        <option value="frame" {"selected" if layout.decorative.kind == 'frame' else ""}>Moldura</option>
                                    </select>
                                </div>
                                <div>
                                    <label style="font-size:11px;">Rótulo Decorativo:</label>
                                    <input name="decorative_label" value="{escape(layout.decorative.label)}" style="font-size:12px;padding:4px;">
                                </div>
                            </div>
                            <div style="margin-top:4px;">
                                <label class="check" style="font-size:11px;color:var(--ink);font-weight:600;">
                                    <input type="checkbox" name="confirm_protected" value="1">
                                    Confirmar explicitamente alteração de atributos protegidos (amarelo)
                                </label>
                            </div>
                        </div>
                    </div>

                    <!-- Painel Vermelho (Critical) -->
                    <div style="background:var(--surface-input);border:1px solid var(--hairline);padding:12px;border-radius:var(--radius-sm);margin-bottom:14px;">
                        <strong style="color:var(--ink);">🔴 Vermelho · Critical (Bloqueado por padrão)</strong>
                        <p class="hint" style="margin:2px 0 8px 0;">Logotipo oficial e regras de integridade. Exige unlock formal auditado.</p>
                        <div style="display:grid;gap:8px;">
                            <div>
                                <label class="check" style="font-size:11px;">
                                    <input type="checkbox" name="logo_locked" value="1" {'checked' if layout.logo.aspect_ratio_locked else ''}>
                                    Proporção do Logotipo Bloqueada (aspect ratio fixo)
                                </label>
                            </div>
                            <div>
                                <label class="check" style="font-size:11px;color:var(--ink);font-weight:600;">
                                    <input type="checkbox" name="unlock_critical" value="1">
                                    Autorizar Desbloqueio de Atributo Crítico (exceção formal)
                                </label>
                            </div>
                            <div>
                                <label style="font-size:11px;">Justificativa da Exceção (auditada):</label>
                                <input name="audit_reason" placeholder="Motivo documentado da alteração crítica..." style="font-size:11px;padding:4px;">
                            </div>
                            <div>
                                <label style="font-size:11px;">Responsável pelo Unlock:</label>
                                <input name="unlocked_by" placeholder="Identificação do solicitante..." style="font-size:11px;padding:4px;">
                            </div>
                        </div>
                    </div>

                    <button type="submit" class="button" style="font-size:13px;padding:8px 16px;width:100%;">Salvar Ajustes de Layout</button>
                </form>

                <!-- Biblioteca de Templates (Seção 30) -->
                <div style="margin-top:18px;background:var(--paper);padding:14px;border-radius:4px;">
                    <strong>Templates de Layout (Seção 30):</strong>
                    <form method="post" action="/api/campaigns/apply_template" style="margin-top:8px;">
                        <input type="hidden" name="campaign_id" value="{cid}">
                        <input type="hidden" name="layout_id" value="{lid}">
                        <input type="hidden" name="slide_id" value="{s_id}">
                        <label style="font-size:11px;">Template Atual: <strong>{tpl_name}</strong></label>
                        <select name="template_id" style="font-size:12px;padding:5px;">
                            {tpl_options}
                        </select>
                        <div style="margin-top:6px;">
                            <label class="check" style="font-size:11px;color:#495057;">
                                <input type="checkbox" name="experimental_authorized" value="1">
                                Autorizar uso de template experimental (obrigatório para experimental)
                            </label>
                        </div>
                        <button type="submit" class="button-secondary" style="font-size:11px;padding:5px 12px;margin-top:6px;">Aplicar Template Selecionado</button>
                    </form>

                    <!-- Salvar como Template -->
                    <details style="margin-top:10px;">
                        <summary style="font-size:12px;padding:2px 0;">Salvar Composição Atual como Novo Template</summary>
                        <form method="post" action="/api/campaigns/save_layout_as_template" style="margin-top:8px;">
                            <input type="hidden" name="campaign_id" value="{cid}">
                            <input type="hidden" name="layout_id" value="{lid}">
                            <input type="hidden" name="slide_id" value="{s_id}">
                            <div class="form-group">
                                <label style="font-size:11px;">Nome do Template</label>
                                <input name="template_name" placeholder="Ex: Editorial Noturno Âmbar" style="font-size:12px;padding:4px;" required>
                            </div>
                            <div class="form-group">
                                <label style="font-size:11px;">Família de Layout</label>
                                <select name="template_family" style="font-size:12px;padding:4px;">
                                    {family_options}
                                </select>
                            </div>
                            <div class="form-group">
                                <label style="font-size:11px;">Estado</label>
                                <select name="template_status" style="font-size:12px;padding:4px;">
                                    <option value="active" selected>Active (Aprovado)</option>
                                    <option value="experimental">Experimental</option>
                                </select>
                            </div>
                            <button type="submit" class="button-secondary" style="font-size:11px;padding:5px 12px;">Salvar como Template</button>
                        </form>
                    </details>
                </div>

                <!-- Histórico de Auditoria -->
                {audit_html}
            </div>
        </div>
    </div>
    '''
    return html


def render_slide_copy_and_audit(app: Application, cid: str, s: Dict[str, Any], query: Optional[Dict[str, Any]] = None) -> str:
    """Renderiza painel de Copy, Legendas e Auditoria Pré-Publicação do Slide (Seções 34-37)."""
    s_id = escape(s['id'])
    copy_obj = app.campaigns.get_or_create_slide_copy(cid, s['id'], initial_caption=s.get('caption_draft', ''))
    prod = app.campaigns.get_product_for_slide(s['id'])
    has_real_price = bool(prod.get('price') or prod.get('preco') or prod.get('valor') or (prod.get('attributes') and (prod['attributes'].get('price') or prod['attributes'].get('preco'))))
    real_price_val = prod.get('price') or prod.get('preco') or prod.get('valor') or ''

    # Executa auditoria do slide
    audit_res = app.campaigns.audit_slide_pre_publish(s['id'])

    # Cards de sugestões
    suggestions_html = ''
    if copy_obj.suggestions:
        cards = []
        for i, sug in enumerate(copy_obj.suggestions):
            s_title = escape(sug.get('title', f'Sugestão {i+1}'))
            s_text = escape(sug.get('text', ''))
            cards.append(f'''
            <div style="background:#fff;border:1px solid var(--line);border-radius:4px;padding:10px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong style="font-size:12px;">{s_title}</strong>
                    <form method="post" action="/api/campaigns/update_slide_copy" style="margin:0;">
                        <input type="hidden" name="campaign_id" value="{cid}">
                        <input type="hidden" name="slide_id" value="{s_id}">
                        <input type="hidden" name="mode" value="suggestions">
                        <input type="hidden" name="text" value="{s_text}">
                        <button type="submit" class="button-secondary" style="font-size:10px;padding:3px 8px;margin:0;">Usar Esta</button>
                    </form>
                </div>
                <p style="font-size:12px;margin:6px 0 0 0;color:#333;">{s_text}</p>
            </div>
            ''')
        suggestions_html = ''.join(cards)

    # Checklist de auditoria
    audit_items_html = []
    for c in audit_res.checks:
        badge_cls = 'badge-success' if c.status == 'passed' else ('status-active' if c.status == 'warning' else 'badge-danger')
        status_label = '✓ Aprovado' if c.status == 'passed' else ('⚠ Alerta' if c.status == 'warning' else '✗ Bloqueado')
        audit_items_html.append(f'''
        <div style="display:flex;justify-content:space-between;align-items:flex-start;padding:6px 0;border-bottom:1px solid #eee;font-size:11px;">
            <div>
                <strong>{escape(c.title)}</strong><br>
                <span style="color:#555;">{escape(c.message)}</span>
                { f"<br><em style='color:#1a73e8;'>Sugestão: {escape(c.fix_suggestion)}</em>" if c.fix_suggestion else "" }
            </div>
            <span class="badge {badge_cls}" style="white-space:nowrap;margin-left:8px;">{status_label}</span>
        </div>
        ''')
    checklist_rendered = ''.join(audit_items_html)

    # Seção de governança de preço
    price_info_html = ''
    if has_real_price:
        price_info_html = f'''
        <p class="hint" style="margin:4px 0 0 0;color:#137333;">
            ✓ Preço real oficial no catálogo: <strong>R$ {escape(str(real_price_val))}</strong>
        </p>
        '''
    else:
        price_info_html = '''
        <p class="hint" style="margin:4px 0 0 0;color:#c5221f;">
            ⚠️ Produto sem preço na Product Bible oficial. Nunca inventar preço (Seções 35 e 37). O toggle de preço será bloqueado se acionado sem dado real.
        </p>
        '''

    audit_badge = '<span class="badge badge-success">✓ Aprovado na Auditoria</span>' if audit_res.is_ready else f'<span class="badge badge-danger">✗ Bloqueado na Auditoria ({len(audit_res.blocked_reasons)} pendências)</span>'

    return f'''
    <div style="margin-top:14px;background:#fcfbf9;border:1px solid #dcd7ce;border-radius:6px;padding:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:14px;">
            <div>
                <span class="tag">Copy, Legenda &amp; Voz · Seções 34-37</span>
                <h4 style="margin:4px 0 0 0;font-size:16px;">Legenda &amp; Governança Editorial · {escape(s['title'])}</h4>
                <p class="hint" style="margin:2px 0 0 0;">Voz brasileira, leve, relaxada e sem rigidez. Sem emojis ou hashtags automáticas.</p>
            </div>
            <div>
                {audit_badge}
            </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
            <!-- Coluna 1: Edição e Modos de Legenda -->
            <div>
                <form method="post" action="/api/campaigns/update_slide_copy">
                    <input type="hidden" name="campaign_id" value="{cid}">
                    <input type="hidden" name="slide_id" value="{s_id}">

                    <div class="form-group">
                        <label>Modo de Legenda (Seção 35):</label>
                        <select name="mode" style="font-size:12px;padding:6px;">
                            <option value="automatic" {"selected" if copy_obj.mode == "automatic" else ""}>automatic (Geração automática alinhada à marca)</option>
                            <option value="suggestions" {"selected" if copy_obj.mode == "suggestions" else ""}>suggestions (Escolha entre 3 sugestões temáticas)</option>
                            <option value="user_provided" {"selected" if copy_obj.mode == "user_provided" else ""}>user_provided (Texto integral fornecido pelo usuário)</option>
                            <option value="ai_plus_user" {"selected" if copy_obj.mode == "ai_plus_user" else ""}>ai_plus_user (IA refina preservando termos do usuário)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Texto da Legenda Atual:</label>
                        <textarea name="text" rows="4" style="font-size:12px;padding:8px;width:100%;font-family:inherit;" required>{escape(copy_obj.text)}</textarea>
                    </div>

                    <div class="form-group">
                        <label>Rascunho / Contribuição do Usuário (para user_provided ou ai_plus_user):</label>
                        <textarea name="user_draft" rows="2" style="font-size:12px;padding:8px;width:100%;font-family:inherit;" placeholder="Digite suas ideias ou rascunho de texto aqui...">{escape(copy_obj.user_draft)}</textarea>
                        <span class="hint">Preservado integralmente sem mutações arbitrárias (M08-A01).</span>
                    </div>

                    <!-- CTA Opcional Contextual (Seção 36) -->
                    <div style="background:var(--paper);padding:10px;border-radius:4px;margin-top:10px;">
                        <strong>CTA Opcional &amp; Contextual (Seção 36):</strong>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:6px;">
                            <div>
                                <label style="font-size:11px;">Modo do CTA</label>
                                <select name="cta_mode" style="font-size:11px;padding:4px;">
                                    <option value="none" {"selected" if copy_obj.cta_mode == "none" else ""}>Nenhum (Opcional)</option>
                                    <option value="automatic" {"selected" if copy_obj.cta_mode == "automatic" else ""}>Automático</option>
                                    <option value="intent_based" {"selected" if copy_obj.cta_mode == "intent_based" else ""}>Baseado em Intenção</option>
                                    <option value="manual" {"selected" if copy_obj.cta_mode == "manual" else ""}>Manual</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size:11px;">Intenção do CTA</label>
                                <select name="cta_intent" style="font-size:11px;padding:4px;">
                                    <option value="descoberta" {"selected" if copy_obj.cta_intent == "descoberta" else ""}>Conhecer Coleção</option>
                                    <option value="aroma" {"selected" if copy_obj.cta_intent == "aroma" else ""}>Escolher Aroma</option>
                                    <option value="presente" {"selected" if copy_obj.cta_intent == "presente" else ""}>Presentear / Casa</option>
                                </select>
                            </div>
                        </div>
                        <div style="margin-top:6px;">
                            <label style="font-size:11px;">Texto Manual do CTA (se modo manual):</label>
                            <input name="cta_text" value="{escape(copy_obj.cta_text)}" style="font-size:11px;padding:4px;" placeholder="Ex: Disponível no link da bio.">
                        </div>
                    </div>

                    <!-- Governança de Preço e Site (Seção 37) -->
                    <div style="background:var(--surface-input);border:1px solid var(--hairline-cool);padding:10px;border-radius:var(--radius-sm);margin-top:12px;">
                        <strong style="color:var(--ink);">Preço e Página de Destino (Seção 37):</strong>
                        <p class="hint" style="margin:2px 0 6px 0;">Não mostrar preço por padrão. Nunca inventar dados comerciais.</p>
                        <div style="margin-bottom:8px;">
                            <label class="check" style="font-size:12px;">
                                <input type="checkbox" name="show_price" value="1" {"checked" if copy_obj.show_price else ""}>
                                Exibir Preço nesta Peça (Requer Justificativa e Aprovação)
                            </label>
                            {price_info_html}
                        </div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                            <div>
                                <label style="font-size:11px;">Justificativa Estratégica (Obrigatória se ativo):</label>
                                <input name="price_justification" value="{escape(copy_obj.price_justification or '')}" style="font-size:11px;padding:4px;" placeholder="Ex: Transparência em lançamento">
                            </div>
                            <div>
                                <label style="font-size:11px;">Aprovador do Preço (Obrigatório se ativo):</label>
                                <input name="price_approved_by" value="{escape(copy_obj.price_approved_by or '')}" style="font-size:11px;padding:4px;" placeholder="Ex: Diretoria Comercial">
                            </div>
                        </div>
                        <div style="margin-top:6px;">
                            <label style="font-size:11px;">URL de Destino / Link da Bio:</label>
                            <input name="destination_url" value="{escape(copy_obj.destination_url or '')}" style="font-size:11px;padding:4px;" placeholder="Ex: https://instagram.com/kiros.sp">
                        </div>
                    </div>

                    <button type="submit" class="button" style="font-size:12px;padding:7px 14px;margin-top:14px;width:100%;">Salvar Legenda e Configurações</button>
                </form>
            </div>

            <!-- Coluna 2: Sugestões Criativas e Auditoria Pré-Publicação -->
            <div>
                <!-- Sugestões Temáticas -->
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <strong>Sugestões Criativas (Seção 35):</strong>
                    <form method="post" action="/api/campaigns/suggest_captions" style="margin:0;">
                        <input type="hidden" name="campaign_id" value="{cid}">
                        <input type="hidden" name="slide_id" value="{s_id}">
                        <button type="submit" class="button-secondary" style="font-size:10px;padding:3px 8px;margin:0;">Gerar Novas ⟳</button>
                    </form>
                </div>
                {suggestions_html}

                <!-- Auditoria Pré-Publicação (M08-A05) -->
                <div style="margin-top:16px;background:#fff;border:1px solid var(--line);border-radius:4px;padding:12px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <strong style="font-size:12px;">Auditoria Pré-Publicação (M08-A05):</strong>
                        <form method="post" action="/api/campaigns/audit_pre_publish" style="margin:0;">
                            <input type="hidden" name="campaign_id" value="{cid}">
                            <input type="hidden" name="slide_id" value="{s_id}">
                            <button type="submit" class="button-secondary" style="font-size:10px;padding:3px 8px;margin:0;">Reauditar 🔍</button>
                        </form>
                    </div>
                    {checklist_rendered}
                </div>
            </div>
        </div>
    </div>
    '''


def render_stories_planner(app: Application, cid: str, query: Optional[Dict[str, Any]] = None) -> str:
    """Renderiza o Planejador Estruturado de Stories com Sequência Própria (Seção 38)."""
    sequences = app.campaigns.list_story_sequences(campaign_id=cid)
    
    seq_cards = []
    for seq in sequences:
        frames_html = []
        for f in seq.frames:
            role_tag = f"<span class='tag'>{escape(f.narrative_role.upper())}</span>"
            inter_tag = f"<span class='badge'>Interação: {escape(f.interaction_type)}</span>" if f.interaction_type != 'none' else ""
            frames_html.append(f'''
            <div style="background:#fff;border:1px solid var(--line);border-radius:4px;padding:10px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong style="font-size:12px;">Frame {f.frame_order}: {escape(f.title)}</strong>
                    <div>{role_tag} {inter_tag}</div>
                </div>
                <p style="font-size:12px;margin:4px 0;font-style:italic;">"{escape(f.overlay_text)}"</p>
                <p class="hint" style="font-size:11px;margin:2px 0;"><strong>Prompt 9:16:</strong> {escape(f.visual_prompt)}</p>
                { f"<p class='hint' style='color:#1a73e8;margin:2px 0;'><strong>Justificativa da Interação:</strong> {escape(f.interaction_justification)}</p>" if f.interaction_justification else "" }
            </div>
            ''')

        audit_res = app.campaigns.audit_story_sequence_pre_publish(seq.id)
        audit_badge = '<span class="badge badge-success">✓ Stories Aprovados</span>' if audit_res.is_ready else f'<span class="badge badge-danger">✗ Bloqueado na Auditoria ({len(audit_res.blocked_reasons)})</span>'

        seq_cards.append(f'''
        <div style="background:#fcfbf9;border:1px solid #dcd7ce;border-radius:6px;padding:16px;margin-top:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:12px;">
                <div>
                    <span class="tag">Sequência de Stories · {escape(seq.story_type)}</span>
                    <h4 style="margin:4px 0 0 0;font-size:16px;">{escape(seq.title)} ({len(seq.frames)} frames narrativos)</h4>
                    <p class="hint" style="margin:2px 0 0 0;">Objetivo: {escape(seq.objective)}</p>
                </div>
                <div>{audit_badge}</div>
            </div>
            {''.join(frames_html)}
        </div>
        ''')

    sequences_content = ''.join(seq_cards) if seq_cards else '<p class="hint">Nenhuma sequência de Stories planejada para esta campanha ainda.</p>'

    return f'''
    <div class="panel" style="margin-top:24px;">
        <span class="tag">Stories · Seção 38</span>
        <h2>Planejador de Stories (Sequência Narrativa Própria)</h2>
        <p class="hint">Stories são conteúdo próprio, não mero redimensionamento do feed. Planejamento de 3 a 5 frames com gancho, contexto e interações contextuais autênticas.</p>

        <!-- Formulário para Criar Nova Sequência -->
        <details class="revision" style="margin-top:12px;">
            <summary>+ Planejar Nova Sequência de Stories</summary>
            <form method="post" action="/api/campaigns/create_story_sequence" class="form-grid" style="margin-top:10px;">
                <input type="hidden" name="campaign_id" value="{cid}">
                <div class="form-group">
                    <label>Título da Sequência</label>
                    <input name="title" placeholder="Ex: Bastidores e Ritual da Manhã" required>
                </div>
                <div class="form-group">
                    <label>Tipo de Story</label>
                    <select name="story_type">
                        <option value="derived_from_campaign" selected>derived_from_campaign (Desdobramento Narrativo da Campanha)</option>
                        <option value="independent">independent (História Independente)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Objetivo da Sequência</label>
                    <input name="objective" placeholder="Ex: Engajamento sensorial e apresentação de rotinas">
                </div>
                <button type="submit" class="button">Gerar Planejamento de Sequência (4 Frames)</button>
            </form>
        </details>

        {sequences_content}
    </div>
    '''


def render_campaign_pre_publish_card(app: Application, cid: str, query: Optional[Dict[str, Any]] = None) -> str:
    """Card de Auditoria Geral Pré-Publicação da Campanha (M08-A05)."""
    audit = app.campaigns.audit_campaign_pre_publish(cid)
    status_badge = '<span class="badge badge-success">✓ Campanha Pronta para Publicação</span>' if audit['is_ready'] else f'<span class="badge badge-danger">✗ Publicação Bloqueada ({len(audit["blocked_reasons"])} pendências)</span>'

    issues_html = ''
    if audit['blocked_reasons']:
        items = ''.join(f'<li>{escape(r)}</li>' for r in audit['blocked_reasons'])
        issues_html = f'''
        <div class="notice warning" style="margin-top:10px;">
            <strong>Pendências Bloqueantes de Pré-Publicação:</strong>
            <ul style="margin:6px 0 0 16px;padding:0;">{items}</ul>
        </div>
        '''

    return f'''
    <div class="panel" style="margin-top:24px;border:2px solid {'#137333' if audit['is_ready'] else '#b06000'};">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div>
                <span class="tag">Governança Editorial &amp; Pré-Publicação · Seções 34-38, 79</span>
                <h3 style="margin:4px 0 0 0;">Checklist de Auditoria Geral Pré-Publicação</h3>
                <p class="hint" style="margin:2px 0 0 0;">Verificação obrigatória antes de qualquer agendamento ou publicação oficial.</p>
            </div>
            <div>
                {status_badge}
            </div>
        </div>
        {issues_html}
    </div>
    '''


