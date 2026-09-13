"""Interface do Calendário Editorial e Publicação Controlada no Instagram (Seções 39, 40, 41, 42, 79)."""
from datetime import datetime, timezone
from html import escape
import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from kiros.application import Application
from kiros.calendar.models import VALID_PILLARS, VALID_PRIORITIES, VALID_CONTENT_TYPES, SEASONAL_PHASES


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
            'msg': f"Sugestão de horário ({rec.recommended_time[:16].replace('T', ' ')}) aplicada via Creative Director.",
        })

    elif action == 'set_time_decision':
        entry_id = data.get('entry_id', '').strip()
        selected_time = data.get('selected_time', '').strip()
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

    html = '<h1>Calendário Editorial</h1>'
    html += '<p class="intro">Controle o ritmo da marca, diversifique pilares temáticos e planeje publicações no Instagram com curadoria assistida do Creative Director e validação humana.</p>'

    if msg:
        html += f'<p role="status" class="notice">{escape(msg)}</p>'
    if err:
        html += f'<p role="alert" class="notice badge-error" style="background:#fbeae5;padding:16px;margin:16px 0;color:#8a2e1d"><strong>Bloqueio:</strong> {escape(err)}</p>'

    # -------------------------------------------------------------------------
    # Status e Limites da Conta do Instagram (M09-A03, M09-A06)
    # -------------------------------------------------------------------------
    if account.connection_status == 'connected':
        status_label = 'Conectado (Ao Vivo)'
        status_badge_cls = 'badge-success'
        status_inline_style = 'background:#e6f4ea;color:#137333;border:1px solid #ceead6;'
        mode_pill = '<span class="badge badge-success" style="background:#e6f4ea;color:#137333;border:1px solid #ceead6;font-weight:600;">● Conexão Real Ativa</span>'
        note_text = 'Conta oficial autenticada e pronta para publicação direta ou agendada. Para gerenciar chaves ou revalidar conexão, acesse <a href="/configuracoes#instagram-credentials">Configurações</a>.'
    elif account.connection_status == 'mock':
        status_label = 'Simulação Mock (Seguro)'
        status_badge_cls = 'status-active'
        status_inline_style = ''
        mode_pill = '<span class="badge" style="background:var(--surface-input);color:var(--ink)">Modo Mock Ativo</span>'
        note_text = 'Ambiente de desenvolvimento seguro: nenhuma chamada de rede externa é disparada sem autorização explícita (Seção 70). Para cadastrar o Token de Acesso da Meta, acesse <a href="/configuracoes#instagram-credentials">Configurações</a>.'
    else:
        status_label = 'Não validado'
        status_badge_cls = 'status-inactive'
        status_inline_style = ''
        mode_pill = '<span class="badge" style="background:var(--surface-input);color:var(--muted)">Não Validado</span>'
        note_text = 'Token ainda não configurado ou não validado. Para cadastrar o Token de Acesso da Meta, acesse <a href="/configuracoes#instagram-credentials">Configurações</a>.'

    html += f'''<div class="panel" style="margin-bottom:24px">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
        <div>
            <span class="tag">Conexão Oficial Instagram (Meta Graph API v20.0+)</span>
            <h2 style="margin:6px 0">Conta: @{escape(account.username or 'usekiros')}</h2>
            <p style="margin:4px 0">Status: <strong class="badge {status_badge_cls}" style="{status_inline_style}">{status_label}</strong> · Cota de Publicação: <strong>{account.rate_limit_remaining}/{account.rate_limit_total} posts / 24h</strong></p>
        </div>
        <div>
            {mode_pill}
        </div>
    </div>
    <div style="margin-top:14px;padding:12px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm);font-size:13px;color:var(--muted);line-height:1.6">
        <strong>Permissões Meta Documentadas:</strong> <code>{', '.join(account.permissions)}</code><br>
        <strong>Formatos Suportados:</strong> Feed (1:1, 4:5; máx 8 MB), Stories (9:16; máx 4 MB). Agendamento oficial: entre 15min e 75 dias.<br>
        <em>{note_text}</em>
    </div>
    </div>'''

    # -------------------------------------------------------------------------
    # Frequência, Limites e Saturação (Seção 40, M09-A01)
    # -------------------------------------------------------------------------
    html += f'''<div class="panel" style="margin-bottom:24px">
    <span class="tag">Ritmo & Governança Editorial</span>
    <h2>Frequência e Restrições de Saturação</h2>
    <p style="color:var(--muted-blue);font-size:14px;max-width:70ch">O Creative Director otimiza as datas dentro dos limites definidos abaixo e alerta imediatamente ao detectar sobreposição temática ou excesso de postagens.</p>
    
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:16px 0">
        <div style="padding:14px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm)">
            <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted)">Limite Semanal</span>
            <h3 style="margin:6px 0;font-size:20px">{prefs.max_posts_per_week} posts/semana</h3>
            <span style="font-size:12px;color:var(--muted)">Capacidade máxima de postagens por semana</span>
        </div>
        <div style="padding:14px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm)">
            <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted)">Intervalo Mínimo</span>
            <h3 style="margin:6px 0;font-size:20px">{prefs.min_hours_between_posts} horas</h3>
            <span style="font-size:12px;color:var(--muted)">Espaçamento de respiro entre postagens</span>
        </div>
        <div style="padding:14px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm)">
            <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted)">Teto por Pilar</span>
            <h3 style="margin:6px 0;font-size:20px">{prefs.saturation_threshold_per_pillar_per_week} posts/semana</h3>
            <span style="font-size:12px;color:var(--muted)">Limite temático para prevenir saturação</span>
        </div>
        <div style="padding:14px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm)">
            <span style="font-size:11px;text-transform:uppercase;font-weight:600;color:var(--muted)">Dias Preferidos</span>
            <h3 style="margin:6px 0;font-size:20px">{', '.join(prefs.preferred_days).upper()}</h3>
            <span style="font-size:12px;color:var(--muted)">Dias prioritários para agendamento</span>
        </div>
    </div>

    <details style="margin-top:16px">
        <summary style="font-size:14px;font-weight:600;color:var(--ink);cursor:pointer">Configurar Limites Semanais e Dias Preferidos</summary>
        <form method="post" action="/api/calendar/save_preferences" style="margin-top:16px;display:grid;gap:14px;max-width:600px">
            <div class="form-group">
                <label for="max_posts_per_week" style="display:block;font-weight:500;margin-bottom:4px">Máximo de posts por semana</label>
                <span class="hint" style="display:block;margin-bottom:6px">Ex: 4 posts para manter cadência regular sem sobrecarga</span>
                <input type="number" id="max_posts_per_week" name="max_posts_per_week" min="1" max="14" value="{prefs.max_posts_per_week}" required>
            </div>
            <div class="form-group">
                <label for="min_hours_between_posts" style="display:block;font-weight:500;margin-bottom:4px">Intervalo mínimo entre posts (horas)</label>
                <span class="hint" style="display:block;margin-bottom:6px">Ex: 24h para espaçar postagens e evitar canibalização de alcance</span>
                <input type="number" id="min_hours_between_posts" name="min_hours_between_posts" min="1" max="168" value="{prefs.min_hours_between_posts}" required>
            </div>
            <div class="form-group">
                <label for="saturation_threshold_per_pillar_per_week" style="display:block;font-weight:500;margin-bottom:4px">Teto de saturação por pilar (posts/semana)</label>
                <span class="hint" style="display:block;margin-bottom:6px">Máximo de repetições da mesma categoria na mesma semana</span>
                <input type="number" id="saturation_threshold_per_pillar_per_week" name="saturation_threshold_per_pillar_per_week" min="1" max="7" value="{prefs.saturation_threshold_per_pillar_per_week}" required>
            </div>
            <div class="form-group">
                <label for="preferred_days" style="display:block;font-weight:500;margin-bottom:4px">Dias preferidos de publicação</label>
                <span class="hint" style="display:block;margin-bottom:6px">Siglas separadas por vírgula (ex: seg, qua, sex, dom)</span>
                <input type="text" id="preferred_days" name="preferred_days" value="{escape(','.join(prefs.preferred_days))}" required>
            </div>
            <div>
                <button type="submit" class="button">Salvar Preferências de Cadência</button>
            </div>
        </form>
    </details>
    </div>'''

    # -------------------------------------------------------------------------
    # Lista de Entradas do Calendário (Seções 39, 41, 42, 79)
    # -------------------------------------------------------------------------
    html += '<div class="panel" style="margin-bottom:24px;max-width:900px" role="region" aria-label="Grade do Calendário">'
    html += '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">'
    html += f'<div><span class="tag">Grade Editorial</span><h2>Itens Planejados ({len(entries)})</h2></div>'
    html += '</div>'

    if not entries:
        html += f'''<div style="text-align:center;padding:36px 20px;border:1px dashed var(--hairline-cool);border-radius:var(--radius-sm);background:var(--surface-input);margin-top:16px">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--muted-blue)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin:0 auto 12px;display:block">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
                <path d="M10 14h4"></path>
                <path d="M12 12v4"></path>
            </svg>
            <h3 style="font-size:16px;margin:0 0 6px;color:var(--ink)">Nenhum item agendado na grade</h3>
            <p style="margin:0 0 16px;color:var(--muted-blue);font-size:13px;max-width:52ch;display:inline-block">Seu calendário editorial está livre no momento. Planeje uma nova peça usando o formulário abaixo ou importe posts aprovados a partir de campanhas.</p>
            <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap">
                <a href="#novo-planejamento" class="button" style="font-size:12px;padding:8px 14px;text-decoration:none">Planejar Novo Item Abaixo</a>
                <a href="/conteudo" class="button button-secondary" style="font-size:12px;padding:8px 14px;text-decoration:none">Ver Campanhas em /conteudo</a>
            </div>
        </div>'''
    else:
        html += '<div style="display:grid;gap:20px;margin-top:20px">'
        for entry in entries:
            # Badges
            status_cls = 'status-active' if entry.status in ('published', 'scheduled') else 'status-inactive'
            pillar_badges = {
                'produtos': 'background:var(--surface-input);color:var(--ink)',
                'lifestyle': 'background:var(--surface-input);color:var(--ink)',
                'marca': 'background:var(--surface-input);color:var(--ink)',
                'educativo': 'background:var(--surface-input);color:var(--ink)',
                'relacionamento': 'background:var(--surface-input);color:var(--ink)',
                'comercial': 'background:var(--surface-input);color:var(--ink)',
                'lancamento': 'background:var(--surface-input);color:var(--ink)',
                'institucional': 'background:var(--surface-input);color:var(--ink)',
                'bastidores': 'background:var(--surface-input);color:var(--ink)',
                'engajamento': 'background:var(--surface-input);color:var(--ink)',
            }
            pillar_style = pillar_badges.get(entry.pillar, 'background:var(--surface-input);color:var(--ink)')

            html += f'''<div class="card" style="padding:20px;border:1px solid var(--hairline);border-radius:var(--radius-sm);background:var(--canvas);margin-bottom:0">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px">
                    <div>
                        <span class="badge" style="{pillar_style};margin-right:6px">{escape(entry.pillar.upper())}</span>
                        <span class="badge" style="background:var(--surface-input);color:var(--ink);margin-right:6px">{escape(entry.content_type.upper())}</span>
                        <span class="badge {status_cls}">{escape(entry.status.upper())}</span>
                        {f'<span class="badge" style="background:var(--surface-input);color:var(--color-primary);margin-left:6px">PRIORIDADE {escape(entry.priority.upper())}</span>' if entry.priority in ('high', 'critical') else ''}
                        {f'<span class="badge" style="background:var(--surface-input);color:var(--muted-blue);margin-left:6px">{escape(entry.seasonal_tag or "")} · {escape(entry.phase or "")}</span>' if entry.seasonal_tag else ''}
                        <h3 style="margin:10px 0 4px;font-size:16px">{escape(entry.title)}</h3>
                        {f'<p style="margin:0 0 8px;font-size:13px;color:var(--muted-blue)">{escape(entry.notes)}</p>' if entry.notes else ''}
                    </div>
                    <div style="text-align:right">
                        <span style="font-size:11px;text-transform:uppercase;color:var(--muted);font-weight:600">Data e Horário:</span><br>
                        <strong style="font-size:14px">{escape(entry.scheduled_for[:16].replace('T', ' ') if entry.scheduled_for else 'Aguardando agendamento')}</strong>
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

                html += f'''<div class="recommendation-box" style="margin:14px 0;background:var(--surface-input);border:1px solid var(--hairline-cool)">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                        <strong style="color:var(--ink)">Recomendação Inteligente do Creative Director:</strong>
                        <span class="badge" style="background:var(--soft);color:var(--ink)">{confidence_pct}% Confiança</span>
                    </div>
                    <p style="margin:6px 0;font-size:13px"><strong>{escape(layer_label)}</strong> · Fonte: <em>{escape(basis.get('source', ''))}</em></p>
                    <p style="margin:6px 0;font-size:13px;color:var(--muted-blue)">{escape(basis.get('reasoning', ''))}</p>
                    <p style="margin:4px 0;font-size:12px;color:var(--muted)"><em>⚠️ {escape(basis.get('disclaimer', ''))}</em></p>
                    <div style="margin-top:8px;font-size:12px">
                        Sugerido: <code>{escape(entry.recommended_time[:16].replace('T', ' ') if entry.recommended_time else '—')}</code> · 
                        Decisão: <strong>{escape(accepted_txt)}</strong>
                    </div>
                </div>'''

            # Ações do Item
            html += '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;align-items:center">'
            
            # Botão Recomendar Horário
            html += f'''<form method="post" action="/api/calendar/recommend_time" class="inline-form" style="margin:0">
                <input type="hidden" name="entry_id" value="{entry.id}">
                <button type="submit" class="button button-secondary" style="margin:0;padding:8px 14px;font-size:13px" title="Solicitar cálculo estatístico de melhor horário">Sugerir Melhor Horário (CD)</button>
            </form>'''

            # Formulário de Horário Manual ("Manual sempre vence" - Seção 41)
            now_def = entry.scheduled_for or (datetime.now(timezone.utc).isoformat()[:16])
            html += f'''<form method="post" action="/api/calendar/set_time_decision" class="inline-form" style="gap:6px;margin:0">
                <input type="hidden" name="entry_id" value="{entry.id}">
                <input type="datetime-local" name="selected_time" value="{now_def[:16]}" aria-label="Definir data e horário manual" style="padding:6px 8px;max-width:200px;font-size:13px" required>
                <input type="hidden" name="accept_recommendation" value="0">
                <button type="submit" class="button button-secondary" style="margin:0;padding:8px 14px;font-size:13px">Salvar Horário Manual</button>
            </form>'''

            # Remover Item
            html += f'''<form method="post" action="/api/calendar/delete_entry" class="inline-form" style="margin:0;margin-left:auto">
                <input type="hidden" name="entry_id" value="{entry.id}">
                <button type="submit" class="button button-danger" style="margin:0;padding:8px 14px;font-size:13px" onclick="return confirm('Remover este post planejado do calendário? Esta ação não pode ser desfeita.')">Remover Item</button>
            </form>'''

            html += '</div>'

            # Caixa de Publicação com Confirmação Explícita (Seção 79)
            if entry.status != 'published':
                html += f'''<details style="margin-top:16px;padding:12px;background:var(--surface-input);border:1px solid var(--hairline);border-radius:var(--radius-sm)">
                    <summary style="font-size:13px;font-weight:600;color:var(--ink);cursor:pointer">
                        Programar ou Publicar no Instagram (Validação Humana Obrigatória)
                    </summary>
                    <form method="post" action="/api/calendar/publish_or_schedule" style="margin-top:12px;display:grid;gap:10px">
                        <input type="hidden" name="entry_id" value="{entry.id}">
                        <div class="form-group">
                            <label for="confirmed_by_{entry.id}" style="display:block;font-size:12px;font-weight:500;margin-bottom:4px">Identificação do Operador Responsável:</label>
                            <span class="hint" style="display:block;margin-bottom:4px">Registrado para fins de auditoria interna e governança</span>
                            <input type="text" id="confirmed_by_{entry.id}" name="confirmed_by" value="Operador KIROS" required>
                        </div>
                        <div class="check" style="margin:8px 0">
                            <input type="checkbox" id="conf_{entry.id}" name="explicit_confirmation" value="1" required>
                            <label for="conf_{entry.id}" style="font-size:13px;font-weight:500;color:var(--ink)">
                                Confirmo expressamente a publicação/agendamento no Instagram deste conteúdo após conferir versão, fidelidade, copy e dados comerciais (Seção 79).
                            </label>
                        </div>
                        <div>
                            <button type="submit" class="button" style="margin-top:4px">Confirmar Agendamento no Instagram</button>
                        </div>
                    </form>
                </details>'''

            html += '</div>'

        html += '</div>'

    html += '</div>'

    # -------------------------------------------------------------------------
    # Formulário para Adicionar Nova Entrada Manual (Seção 39)
    # -------------------------------------------------------------------------
    html += '''<div id="novo-planejamento" class="panel" style="max-width:700px">
    <span class="tag">Novo Planejamento</span>
    <h2>Adicionar Entrada ao Calendário</h2>
    <p style="color:var(--muted-blue);font-size:13px;margin:4px 0 14px">Cadastre uma nova peça editorial com fuso horário, formato específico e classificação por pilar aromático.</p>
    <form method="post" action="/api/calendar/create_entry" style="display:grid;gap:12px">
        <div class="form-group">
            <label for="title" style="display:block;font-weight:500;margin-bottom:4px">Título do Conteúdo / Post</label>
            <input type="text" id="title" name="title" placeholder="Ex: Lançamento Difusor Lavanda Real (Feed)" required>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group">
                <label for="content_type" style="display:block;font-weight:500;margin-bottom:4px">Formato</label>
                <select id="content_type" name="content_type">
                    <option value="feed">Feed (Imagem 1:1 / 4:5)</option>
                    <option value="carousel">Carrossel (2 a 10 slides)</option>
                    <option value="stories">Stories (9:16)</option>
                    <option value="reels">Reels (Vídeo vertical)</option>
                </select>
            </div>
            <div class="form-group">
                <label for="pillar" style="display:block;font-weight:500;margin-bottom:4px">Pilar Editorial</label>
                <select id="pillar" name="pillar">
                    <option value="institucional">Institucional (Conceito e essência da marca)</option>
                    <option value="lancamento">Lançamento (Novas fragrâncias e coleções)</option>
                    <option value="educativo">Educativo (Notas olfativas e rituais de uso)</option>
                    <option value="bastidores">Bastidores (Processo artesanal e atelier)</option>
                    <option value="engajamento">Engajamento (Comunidade, enquetes e perguntas)</option>
                    <option value="lifestyle">Lifestyle (Decoração, bem-estar e aconchego)</option>
                </select>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group">
                <label for="priority" style="display:block;font-weight:500;margin-bottom:4px">Prioridade</label>
                <select id="priority" name="priority">
                    <option value="low">Baixa (Flexível na grade)</option>
                    <option value="medium" selected>Média (Cadência normal)</option>
                    <option value="high">Alta (Data comemorativa ou marco)</option>
                    <option value="critical">Crítica (Data prioritária com fuso reservado)</option>
                </select>
            </div>
            <div class="form-group">
                <label for="scheduled_for" style="display:block;font-weight:500;margin-bottom:4px">Data e Horário Pretendido</label>
                <input type="datetime-local" id="scheduled_for" name="scheduled_for">
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group">
                <label for="seasonal_tag" style="display:block;font-weight:500;margin-bottom:4px">Tag Sazonal (Opcional)</label>
                <input type="text" id="seasonal_tag" name="seasonal_tag" placeholder="Ex: dia_das_maes, primavera">
            </div>
            <div class="form-group">
                <label for="phase" style="display:block;font-weight:500;margin-bottom:4px">Fase Sazonal</label>
                <select id="phase" name="phase">
                    <option value="none">Nenhuma (Conteúdo contínuo / Evergreen)</option>
                    <option value="warm_up">1. Aquecimento (Warm-up / Antecipação)</option>
                    <option value="consideracao">2. Consideração (Apresentação dos benefícios)</option>
                    <option value="conversao">3. Conversão (Disponibilidade e compra)</option>
                    <option value="last_call">4. Encerramento (Last Call / Últimos dias)</option>
                </select>
            </div>
        </div>
        <div class="form-group">
            <label for="notes" style="display:block;font-weight:500;margin-bottom:4px">Notas Estratégicas e Contexto</label>
            <textarea id="notes" name="notes" rows="2" placeholder="Observações e direcionamentos para o Creative Director"></textarea>
        </div>
        <div>
            <button type="submit" class="button">Salvar Entrada no Calendário</button>
        </div>
    </form>
    </div>'''

    return html

