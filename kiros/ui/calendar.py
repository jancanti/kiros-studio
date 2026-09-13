"""Interface do Calendário Editorial e Publicação Controlada no Instagram (Seções 39, 40, 41, 42, 79)."""
from datetime import datetime, timezone
from html import escape
import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from kiros.application import Application
from kiros.calendar.models import VALID_PILLARS, VALID_PRIORITIES, VALID_CONTENT_TYPES, SEASONAL_PHASES
from kiros.tz import now_sp, format_sp_display, format_sp_input, ensure_sp_iso, normalize_input_sp_iso


def dispatch_calendar_action(app: Application, action: str, data: Dict[str, str]) -> str:
    """Processa ações submetidas no Calendário via POST."""
    calendar = app.calendar
    publisher = app.publisher

    if action == 'save_preferences':
        max_posts = int(data.get('max_posts_per_week', '4'))
        min_hours = int(data.get('min_hours_between_posts', '24'))
        saturation_threshold = int(data.get('saturation_threshold_per_pillar_per_week', '2'))
        days = [d.strip() for d in data.get('preferred_days', 'seg,qua,sex,dom').split(',') if d.strip()]

        calendar.save_preferences(
            max_posts_per_week=max_posts,
            min_hours_between_posts=min_hours,
            preferred_days=days,
            saturation_threshold=saturation_threshold,
        )
        return urlencode({'saved_prefs': '1', 'msg': 'Preferências de cadência e limites semanais salvas com sucesso.'})

    elif action == 'create_entry':
        title = data.get('title', '').strip()
        content_type = data.get('content_type', 'feed')
        pillar = data.get('pillar', 'institucional')
        priority = data.get('priority', 'medium')
        campaign_id = data.get('campaign_id', '').strip() or None
        scheduled_for = data.get('scheduled_for', '').strip() or None
        if scheduled_for:
            scheduled_for = normalize_input_sp_iso(scheduled_for)
        seasonal_tag = data.get('seasonal_tag', '').strip() or None
        phase = data.get('phase', 'none').strip() or 'none'
        notes = data.get('notes', '').strip()

        entry = calendar.create_entry(
            title=title,
            content_type=content_type,
            pillar=pillar,
            priority=priority,
            campaign_id=campaign_id,
            scheduled_for=scheduled_for,
            seasonal_tag=seasonal_tag,
            phase=phase,
            notes=notes,
        )
        return urlencode({'created_entry': entry.id, 'msg': f"Conteúdo '{title}' agendado com sucesso no calendário."})

    elif action == 'delete_entry':
        entry_id = data.get('entry_id', '').strip()
        calendar.delete_entry(entry_id)
        return urlencode({'msg': 'Item removido do calendário editorial.'})

    elif action == 'recommend_time':
        entry_id = data.get('entry_id', '').strip()
        entry = calendar.get_entry(entry_id)
        if not entry:
            raise KeyError(f'Entrada {entry_id} não encontrada.')

        rec = calendar.recommend_best_time(
            campaign_id=entry.campaign_id,
            content_type=entry.content_type,
            pillar=entry.pillar,
            preferred_date=entry.scheduled_for,
        )

        calendar.record_time_decision(
            entry_id=entry_id,
            selected_time_iso=rec.recommended_time,
            accept_recommendation=True,
        )
        return urlencode({
            'entry_id': entry_id,
            'msg': f"Sugestão de horário ({format_sp_display(rec.recommended_time)}) aplicada via Creative Director.",
        })

    elif action == 'set_time_decision':
        entry_id = data.get('entry_id', '').strip()
        selected_time = data.get('selected_time', '').strip()
        if selected_time:
            selected_time = normalize_input_sp_iso(selected_time)
        accept_rec = data.get('accept_recommendation') == '1'

        calendar.record_time_decision(
            entry_id=entry_id,
            selected_time_iso=selected_time,
            accept_recommendation=accept_rec,
        )
        mode_txt = 'Recomendação aceita' if accept_rec else 'Horário manual definido (Manual venceu)'
        return urlencode({'entry_id': entry_id, 'msg': f"Decisão registrada: {mode_txt}."})

    elif action == 'publish_or_schedule':
        entry_id = data.get('entry_id', '').strip()
        entry = calendar.get_entry(entry_id)
        if not entry:
            raise KeyError(f'Entrada {entry_id} não encontrada.')

        explicit_conf = data.get('explicit_confirmation') == '1'
        confirmed_by = data.get('confirmed_by', '').strip()
        asset_id = data.get('asset_id', '').strip() or f"asset_{entry.id}"
        caption = data.get('caption', '').strip() or entry.title

        # Publica ou agenda através do SocialPublisher
        post_id = publisher.publish(
            asset_id=asset_id,
            caption=caption,
            campaign_id=entry.campaign_id,
            slide_id=entry.slide_id,
            calendar_entry_id=entry.id,
            media_type='STORIES' if entry.content_type == 'stories' else 'IMAGE',
            aspect_ratio='9:16' if entry.content_type == 'stories' else '1:1',
            scheduled_time_iso=entry.scheduled_for,
            explicit_confirmation=explicit_conf,
            confirmed_by=confirmed_by,
        )
        return urlencode({
            'published_id': post_id,
            'msg': f"Publicação/agendamento no Instagram processado com sucesso (ID: {post_id}). Confirmação explícita registrada.",
        })

    raise ValueError(f'Ação de calendário desconhecida: {action}')


def render_calendar(app: Application, query: Dict[str, Any]) -> str:
    """Renderiza a página /calendario."""
    calendar = app.calendar
    publisher = app.publisher
    prefs = calendar.get_preferences()
    entries = calendar.list_entries()
    account = publisher.get_account_status()

    msg = query.get('msg', [''])[0] if isinstance(query.get('msg'), list) else query.get('msg', '')
    err = query.get('error', [''])[0] if isinstance(query.get('error'), list) else query.get('error', '')

    html = '<div class="calendar-header" style="margin-bottom:28px;">'
    html += '<h1 style="margin:0 0 10px;font-size:28px;font-weight:600;letter-spacing:-0.6px;">Calendário Editorial</h1>'
    html += '<p class="intro" style="color:var(--muted-blue);font-size:14.5px;line-height:1.7;margin:0;max-width:75ch;">Controle o ritmo da marca, diversifique pilares temáticos e planeje publicações no Instagram com curadoria assistida do Creative Director e validação humana.</p>'
    html += '</div>'

    if msg:
        html += f'<p role="status" class="notice" style="margin-bottom:24px;">{escape(msg)}</p>'
    if err:
        html += f'<p role="alert" class="notice badge-error" style="background:#fbeae5;padding:16px;margin-bottom:24px;color:#8a2e1d"><strong>Bloqueio:</strong> {escape(err)}</p>'

    # -------------------------------------------------------------------------
    # 1. Status Bar Slim da Conta do Instagram (Meta Graph API v20.0+)
    # -------------------------------------------------------------------------
    if account.connection_status == 'connected':
        status_label = 'Conectado (Ao Vivo)'
        status_badge_cls = 'badge-success'
        status_inline_style = 'background:#e6f4ea;color:#137333;border:1px solid #ceead6;'
        mode_pill = '<span class="badge badge-success" style="background:#e6f4ea;color:#137333;border:1px solid #ceead6;font-weight:600;">● Conexão Real Ativa</span>'
    elif account.connection_status == 'mock':
        status_label = 'Simulação Mock (Seguro)'
        status_badge_cls = 'status-active'
        status_inline_style = ''
        mode_pill = '<span class="badge" style="background:var(--surface-input);color:var(--ink)">Modo Mock Ativo</span>'
    else:
        status_label = 'Não validado'
        status_badge_cls = 'status-inactive'
        status_inline_style = ''
        mode_pill = '<span class="badge" style="background:var(--surface-input);color:var(--muted)">Não Validado</span>'

    html += f'''
    <div class="calendar-status-bar">
        <div class="calendar-status-info">
            <span class="tag" style="margin:0;font-size:10px;">Meta Graph API v20.0+</span>
            <strong style="font-size:15px;color:var(--ink);">Conta: @{escape(account.username or 'usekiros')}</strong>
            <span class="badge {status_badge_cls}" style="{status_inline_style}">{status_label}</span>
            <span class="calendar-status-meta">Cota de Publicação: <strong>{account.rate_limit_remaining}/{account.rate_limit_total} posts / 24h</strong></span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
            {mode_pill}
            <a href="/configuracoes#instagram-credentials" class="button-secondary" style="font-size:12px;padding:6px 14px;min-height:34px;text-decoration:none;">Gerenciar</a>
        </div>
    </div>
    '''

    # -------------------------------------------------------------------------
    # 2. PROTAGONISTA: Grade Editorial & Fila de Publicações (Seções 39, 41, 42, 79)
    # -------------------------------------------------------------------------
    html += '<div class="calendar-main-panel" role="region" aria-label="Grade do Calendário">'
    html += '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;border-bottom:1px solid var(--hairline);padding-bottom:16px;margin-bottom:24px;">'
    html += f'<div><span class="tag">Grade Editorial</span><h2 style="margin:4px 0 0;font-size:20px;">Itens Planejados ({len(entries)})</h2></div>'
    html += '<div style="display:flex;gap:10px;align-items:center;">'
    html += '<a href="#novo-planejamento" class="button" style="margin:0;font-size:13px;padding:8px 16px;">+ Novo Agendamento</a>'
    html += '<a href="/conteudo" class="button-secondary" style="margin:0;font-size:13px;padding:8px 16px;text-decoration:none;">Ver Campanhas</a>'
    html += '</div></div>'

    if not entries:
        html += f'''<div style="text-align:center;padding:48px 24px;border:1px dashed var(--hairline-cool);border-radius:var(--radius-sm);background:var(--surface-input);margin-top:12px">
            <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="var(--muted-blue)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin:0 auto 14px;display:block">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
                <path d="M10 14h4"></path>
                <path d="M12 12v4"></path>
            </svg>
            <h3 style="font-size:17px;font-weight:600;margin:0 0 8px;color:var(--ink)">Nenhum item agendado na grade</h3>
            <p style="margin:0 0 20px;color:var(--muted-blue);font-size:14px;line-height:1.6;max-width:54ch;display:inline-block">Seu calendário editorial está livre no momento. Planeje uma nova peça usando o formulário abaixo ou importe posts aprovados a partir de campanhas.</p>
            <div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap">
                <a href="#novo-planejamento" class="button" style="font-size:13px;padding:8px 16px;text-decoration:none">Planejar Novo Item Abaixo</a>
                <a href="/conteudo" class="button button-secondary" style="font-size:13px;padding:8px 16px;text-decoration:none">Ver Campanhas em /conteudo</a>
            </div>
        </div>'''
    else:
        html += '<div style="display:grid;gap:24px;margin-top:20px">'
        for entry in entries:
            status_cls = 'status-active' if entry.status in ('published', 'scheduled') else 'status-inactive'
            pillar_style = 'background:var(--surface-input);color:var(--ink)'

            html += f'''<div class="calendar-post-card">
                <div class="calendar-post-header">
                    <div>
                        <span class="badge" style="{pillar_style};margin-right:6px">{escape(entry.pillar.upper())}</span>
                        <span class="badge" style="background:var(--surface-input);color:var(--ink);margin-right:6px">{escape(entry.content_type.upper())}</span>
                        <span class="badge {status_cls}">{escape(entry.status.upper())}</span>
                        {f'<span class="badge" style="background:var(--surface-input);color:var(--color-primary);margin-left:6px">PRIORIDADE {escape(entry.priority.upper())}</span>' if entry.priority in ('high', 'critical') else ''}
                        {f'<span class="badge" style="background:var(--surface-input);color:var(--muted-blue);margin-left:6px">{escape(entry.seasonal_tag or "")} · {escape(entry.phase or "")}</span>' if entry.seasonal_tag else ''}
                        <h3 class="calendar-post-title">{escape(entry.title)}</h3>
                        {f'<p class="calendar-post-notes">{escape(entry.notes)}</p>' if entry.notes else ''}
                    </div>
                    <div class="calendar-time-badge">
                        <span class="calendar-time-label">Data e Horário:</span>
                        <strong class="calendar-time-val">{escape(format_sp_display(entry.scheduled_for) if entry.scheduled_for else 'Aguardando agendamento')}</strong>
                    </div>
                </div>'''

            # Recomendações em Camadas (Seções 41 e 42)
            if entry.data_basis:
                basis = entry.data_basis
                layer_label = {
                    'kiros': 'Camada 1: KIROS (Dados Próprios da Marca)',
                    'setor': 'Camada 2: Setor (Benchmark Cosméticos & Aromas)',
                    'plataforma_geral': 'Camada 3: Plataforma Geral (Instagram Brasil)',
                }.get(basis.get('layer', ''), basis.get('layer', ''))

                confidence_pct = int(basis.get('confidence', 0.5) * 100)
                accepted_txt = 'Aceito pelo usuário' if entry.time_accepted else 'Horário manual definido (Manual venceu)'

                html += f'''<div class="calendar-recommendation-box">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                        <strong style="color:var(--ink);font-size:13.5px">Recomendação Inteligente do Creative Director:</strong>
                        <span class="badge" style="background:var(--canvas);color:var(--ink);border:1px solid var(--hairline)">{confidence_pct}% Confiança</span>
                    </div>
                    <p style="margin:8px 0 4px;font-size:13px"><strong>{escape(layer_label)}</strong> · Fonte: <em>{escape(basis.get('source', ''))}</em></p>
                    <p style="margin:4px 0 6px;font-size:13px;color:var(--muted-blue);line-height:1.5">{escape(basis.get('reasoning', ''))}</p>
                    <p style="margin:4px 0;font-size:12px;color:var(--muted)"><em>⚠️ {escape(basis.get('disclaimer', ''))}</em></p>
                    <div style="margin-top:10px;font-size:12.5px;color:var(--ink)">
                        Sugerido: <code>{escape(format_sp_display(entry.recommended_time) if entry.recommended_time else '—')}</code> · 
                        Decisão: <strong>{escape(accepted_txt)}</strong>
                    </div>
                </div>'''

            # Ações do Item
            html += '<div class="calendar-action-row">'
            
            # Botão Recomendar Horário
            html += f'''<form method="post" action="/api/calendar/recommend_time" class="inline-form" style="margin:0">
                <input type="hidden" name="entry_id" value="{entry.id}">
                <button type="submit" class="button-secondary" style="margin:0;padding:8px 14px;font-size:13px" title="Solicitar cálculo estatístico de melhor horário">Sugerir Melhor Horário (CD)</button>
            </form>'''

            # Formulário de Horário Manual ("Manual sempre vence" - Seção 41)
            now_def = format_sp_input(entry.scheduled_for or now_sp())
            html += f'''<form method="post" action="/api/calendar/set_time_decision" class="inline-form" style="gap:8px;margin:0">
                <input type="hidden" name="entry_id" value="{entry.id}">
                <input type="datetime-local" name="selected_time" value="{now_def}" aria-label="Definir data e horário manual" style="padding:6px 10px;max-width:210px;font-size:13px" required>
                <input type="hidden" name="accept_recommendation" value="0">
                <button type="submit" class="button-secondary" style="margin:0;padding:8px 14px;font-size:13px">Salvar Horário Manual</button>
            </form>'''

            # Remover Item
            html += f'''<form method="post" action="/api/calendar/delete_entry" class="inline-form" style="margin:0;margin-left:auto">
                <input type="hidden" name="entry_id" value="{entry.id}">
                <button type="submit" class="button-danger" style="margin:0;padding:8px 14px;font-size:13px" onclick="return confirm('Remover este post planejado do calendário? Esta ação não pode ser desfeita.')">Remover Item</button>
            </form>'''

            html += '</div>'

            # Caixa de Publicação com Confirmação Explícita (Seção 79)
            if entry.status != 'published':
                html += f'''<details style="margin-top:18px;padding:16px;background:var(--surface-input);border:1px solid var(--hairline-cool);border-radius:var(--radius-sm)">
                    <summary style="font-size:13.5px;font-weight:600;color:var(--ink);cursor:pointer">
                        Programar ou Publicar no Instagram (Validação Humana Obrigatória)
                    </summary>
                    <form method="post" action="/api/calendar/publish_or_schedule" style="margin-top:14px;display:grid;gap:12px">
                        <input type="hidden" name="entry_id" value="{entry.id}">
                        <div class="form-group" style="margin:0;">
                            <label for="confirmed_by_{entry.id}" style="display:block;font-size:12.5px;font-weight:500;margin-bottom:4px">Identificação do Operador Responsável:</label>
                            <span class="hint" style="display:block;margin-bottom:6px">Registrado para fins de auditoria interna e governança</span>
                            <input type="text" id="confirmed_by_{entry.id}" name="confirmed_by" value="Operador KIROS" required>
                        </div>
                        <div class="check" style="margin:8px 0">
                            <input type="checkbox" id="conf_{entry.id}" name="explicit_confirmation" value="1" required>
                            <label for="conf_{entry.id}" style="font-size:13px;line-height:1.5;font-weight:500;color:var(--ink)">
                                Confirmo expressamente a publicação/agendamento no Instagram deste conteúdo após conferir versão, fidelidade, copy e dados comerciais (Seção 79).
                            </label>
                        </div>
                        <div>
                            <button type="submit" class="button" style="margin:0">Confirmar Agendamento no Instagram</button>
                        </div>
                    </form>
                </details>'''

            html += '</div>'

        html += '</div>'

    html += '</div>' # fecha calendar-main-panel

    # -------------------------------------------------------------------------
    # 3. ZONA SECUNDÁRIA: Novo Planejamento (Esquerda) + Cadência & Frequência (Direita)
    # -------------------------------------------------------------------------
    html += '<div class="calendar-secondary-grid">'

    # Coluna Esquerda: Novo Planejamento (Formulário)
    html += '''<div class="calendar-col">
    <div id="novo-planejamento" class="panel">
        <span class="tag">Novo Planejamento</span>
        <h2 style="margin:6px 0 4px;font-size:20px;">Adicionar Entrada ao Calendário</h2>
        <p style="color:var(--muted-blue);font-size:13.5px;line-height:1.6;margin:0 0 18px;">Cadastre uma nova peça editorial com fuso horário, formato específico e classificação por pilar aromático.</p>
        <form method="post" action="/api/calendar/create_entry" style="display:grid;gap:14px;margin-top:0;">
            <div class="form-group" style="margin:0;">
                <label for="title" style="display:block;font-weight:500;margin-bottom:4px">Título do Conteúdo / Post</label>
                <input type="text" id="title" name="title" placeholder="Ex: Lançamento Difusor Lavanda Real (Feed)" required style="max-width:100%;">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
                <div class="form-group" style="margin:0;">
                    <label for="content_type" style="display:block;font-weight:500;margin-bottom:4px">Formato</label>
                    <select id="content_type" name="content_type" style="max-width:100%;">
                        <option value="feed">Feed (Imagem 1:1 / 4:5)</option>
                        <option value="carousel">Carrossel (2 a 10 slides)</option>
                        <option value="stories">Stories (9:16)</option>
                        <option value="reels">Reels (Vídeo vertical)</option>
                    </select>
                </div>
                <div class="form-group" style="margin:0;">
                    <label for="pillar" style="display:block;font-weight:500;margin-bottom:4px">Pilar Editorial</label>
                    <select id="pillar" name="pillar" style="max-width:100%;">
                        <option value="institucional">Institucional (Conceito e essência)</option>
                        <option value="lancamento">Lançamento (Novas fragrâncias)</option>
                        <option value="educativo">Educativo (Notas olfativas e rituais)</option>
                        <option value="bastidores">Bastidores (Processo artesanal)</option>
                        <option value="engajamento">Engajamento (Comunidade e perguntas)</option>
                        <option value="lifestyle">Lifestyle (Decoração e aconchego)</option>
                    </select>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
                <div class="form-group" style="margin:0;">
                    <label for="priority" style="display:block;font-weight:500;margin-bottom:4px">Prioridade</label>
                    <select id="priority" name="priority" style="max-width:100%;">
                        <option value="low">Baixa (Flexível na grade)</option>
                        <option value="medium" selected>Média (Cadência normal)</option>
                        <option value="high">Alta (Data comemorativa ou marco)</option>
                        <option value="critical">Crítica (Data prioritária com fuso)</option>
                    </select>
                </div>
                <div class="form-group" style="margin:0;">
                    <label for="scheduled_for" style="display:block;font-weight:500;margin-bottom:4px">Data e Horário Pretendido (Fuso São Paulo · 24h)</label>
                    <input type="datetime-local" id="scheduled_for" name="scheduled_for" value="{format_sp_input(now_sp())}" style="max-width:100%;">
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
                <div class="form-group" style="margin:0;">
                    <label for="seasonal_tag" style="display:block;font-weight:500;margin-bottom:4px">Tag Sazonal (Opcional)</label>
                    <input type="text" id="seasonal_tag" name="seasonal_tag" placeholder="Ex: dia_das_maes, natal" style="max-width:100%;">
                </div>
                <div class="form-group" style="margin:0;">
                    <label for="phase" style="display:block;font-weight:500;margin-bottom:4px">Fase Sazonal</label>
                    <select id="phase" name="phase" style="max-width:100%;">
                        <option value="none">Nenhuma (Conteúdo contínuo)</option>
                        <option value="warm_up">1. Aquecimento (Warm-up)</option>
                        <option value="consideracao">2. Consideração</option>
                        <option value="conversao">3. Conversão</option>
                        <option value="last_call">4. Encerramento (Last Call)</option>
                    </select>
                </div>
            </div>
            <div class="form-group" style="margin:0;">
                <label for="notes" style="display:block;font-weight:500;margin-bottom:4px">Notas Estratégicas e Contexto</label>
                <textarea id="notes" name="notes" rows="2" placeholder="Observações e direcionamentos para o Creative Director" style="max-width:100%;"></textarea>
            </div>
            <div style="margin-top:6px;">
                <button type="submit" class="button" style="width:100%;margin:0;">Salvar Entrada no Calendário</button>
            </div>
        </form>
    </div>
    </div>'''

    # Coluna Direita: Ritmo & Governança de Frequência (Seção 40, M09-A01)
    html += f'''<div class="calendar-col">
    <div class="panel">
        <span class="tag">Ritmo & Governança Editorial</span>
        <h2 style="margin:6px 0 4px;font-size:20px;">Frequência e Restrições de Saturação</h2>
        <p style="color:var(--muted-blue);font-size:13.5px;line-height:1.6;margin:0 0 16px;">O Creative Director otimiza as datas dentro dos limites definidos abaixo e alerta imediatamente ao detectar sobreposição temática ou excesso de postagens.</p>
        
        <div class="calendar-cadence-grid">
            <div class="calendar-cadence-card">
                <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted-blue)">Limite Semanal</span>
                <div class="calendar-cadence-val">{prefs.max_posts_per_week} posts/sem</div>
                <span style="font-size:12px;color:var(--muted)">Capacidade máxima</span>
            </div>
            <div class="calendar-cadence-card">
                <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted-blue)">Intervalo Mínimo</span>
                <div class="calendar-cadence-val">{prefs.min_hours_between_posts} horas</div>
                <span style="font-size:12px;color:var(--muted)">Respiro entre posts</span>
            </div>
            <div class="calendar-cadence-card">
                <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted-blue)">Teto por Pilar</span>
                <div class="calendar-cadence-val">{prefs.saturation_threshold_per_pillar_per_week} posts/sem</div>
                <span style="font-size:12px;color:var(--muted)">Prevenção de saturação</span>
            </div>
            <div class="calendar-cadence-card">
                <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted-blue)">Dias Preferidos</span>
                <div class="calendar-cadence-val" style="font-size:15px;">{', '.join(prefs.preferred_days).upper()}</div>
                <span style="font-size:12px;color:var(--muted)">Dias prioritários</span>
            </div>
        </div>

        <details style="margin-top:20px;padding:14px;background:var(--surface-input);border:1px solid var(--hairline-cool);border-radius:var(--radius-sm)">
            <summary style="font-size:13.5px;font-weight:600;color:var(--ink);cursor:pointer">Configurar Limites Semanais e Dias Preferidos</summary>
            <form method="post" action="/api/calendar/save_preferences" style="margin-top:16px;display:grid;gap:14px;max-width:100%">
                <div class="form-group" style="margin:0;">
                    <label for="max_posts_per_week" style="display:block;font-weight:500;margin-bottom:4px">Máximo de posts por semana</label>
                    <span class="hint" style="display:block;margin-bottom:6px">Ex: 4 posts para manter cadência regular sem sobrecarga</span>
                    <input type="number" id="max_posts_per_week" name="max_posts_per_week" min="1" max="14" value="{prefs.max_posts_per_week}" required style="max-width:100%;">
                </div>
                <div class="form-group" style="margin:0;">
                    <label for="min_hours_between_posts" style="display:block;font-weight:500;margin-bottom:4px">Intervalo mínimo entre posts (horas)</label>
                    <span class="hint" style="display:block;margin-bottom:6px">Ex: 24h para espaçar postagens e evitar canibalização de alcance</span>
                    <input type="number" id="min_hours_between_posts" name="min_hours_between_posts" min="1" max="168" value="{prefs.min_hours_between_posts}" required style="max-width:100%;">
                </div>
                <div class="form-group" style="margin:0;">
                    <label for="saturation_threshold_per_pillar_per_week" style="display:block;font-weight:500;margin-bottom:4px">Teto de saturação por pilar (posts/semana)</label>
                    <span class="hint" style="display:block;margin-bottom:6px">Máximo de repetições da mesma categoria na mesma semana</span>
                    <input type="number" id="saturation_threshold_per_pillar_per_week" name="saturation_threshold_per_pillar_per_week" min="1" max="7" value="{prefs.saturation_threshold_per_pillar_per_week}" required style="max-width:100%;">
                </div>
                <div class="form-group" style="margin:0;">
                    <label for="preferred_days" style="display:block;font-weight:500;margin-bottom:4px">Dias preferidos de publicação</label>
                    <span class="hint" style="display:block;margin-bottom:6px">Siglas separadas por vírgula (ex: seg, qua, sex, dom)</span>
                    <input type="text" id="preferred_days" name="preferred_days" value="{escape(','.join(prefs.preferred_days))}" required style="max-width:100%;">
                </div>
                <div style="margin-top:6px;">
                    <button type="submit" class="button" style="width:100%;margin:0;">Salvar Preferências de Cadência</button>
                </div>
            </form>
        </details>
    </div>
    </div>'''

    html += '</div>' # fecha calendar-secondary-grid

    return html

