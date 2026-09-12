"""Serviço de Dashboard Contextual (Seção 59).

Reúne informações dos serviços existentes sem duplicar lógica:
- Hoje
- Oportunidade
- Próximo passo recomendado
- Calendário
- Criação
- Aprendizados
"""
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DashboardService:
    """Consolida os dados contextuais das 6 dimensões do estúdio."""

    def __init__(
        self,
        database,
        library,
        campaigns,
        queue,
        calendar,
        idea_bank=None,
        learning=None,
        prompt_library=None,
    ):
        self.db = database
        self.library = library
        self.campaigns = campaigns
        self.queue = queue
        self.calendar = calendar
        self.idea_bank = idea_bank
        self.learning = learning
        self.prompt_library = prompt_library

    def get_dashboard_data(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        hoje_data = self._build_hoje(now)
        oportunidade_data = self._build_oportunidade(now)
        calendario_data = self._build_calendario(now)
        criacao_data = self._build_criacao()
        aprendizados_data = self._build_aprendizados()
        proximo_passo_data = self._build_proximo_passo(
            hoje=hoje_data,
            criacao=criacao_data,
            calendario=calendario_data,
            aprendizados=aprendizados_data,
        )

        return {
            'hoje': hoje_data,
            'oportunidade': oportunidade_data,
            'proximo_passo': proximo_passo_data,
            'calendario': calendario_data,
            'criacao': criacao_data,
            'aprendizados': aprendizados_data,
        }

    def _build_hoje(self, now: datetime) -> Dict[str, Any]:
        meses = [
            'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
        ]
        data_formatada = f"{now.day} de {meses[now.month - 1]} de {now.year}"

        queue_paused = False
        pending_jobs = 0
        completed_jobs = 0

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row_pref = conn.execute("SELECT value FROM preferences WHERE key = 'execution_queue_paused'").fetchone()
            if row_pref and row_pref['value'] == 'true':
                queue_paused = True

            try:
                pending_jobs = conn.execute("SELECT COUNT(*) FROM execution_jobs WHERE status IN ('pending', 'processing')").fetchone()[0]
                completed_jobs = conn.execute("SELECT COUNT(*) FROM execution_jobs WHERE status = 'completed'").fetchone()[0]
            except Exception:
                pass

        return {
            'data_formatada': data_formatada,
            'queue_paused': queue_paused,
            'queue_status': 'Pausada' if queue_paused else 'Ativa',
            'pending_jobs': pending_jobs,
            'completed_jobs': completed_jobs,
            'mode': 'Simulação local (mock)',
        }

    def _build_oportunidade(self, now: datetime) -> Dict[str, Any]:
        # Tenta extrair datas sazonais ou produtos com estoque sem campanha
        date_str = now.strftime('%Y-%m-%d')
        priorities = []
        if self.idea_bank and hasattr(self.idea_bank, 'priorities_for_date'):
            try:
                priorities = self.idea_bank.priorities_for_date(date_str)
            except Exception:
                priorities = []

        if priorities:
            top = priorities[0]
            return {
                'title': f"Sazonalidade: {top.get('title', 'Oportunidade Comercial')}",
                'description': top.get('reason', 'Planejamento editorial antecipado recomendado.'),
                'recommended_pillar': top.get('pillar', 'Lifestyle'),
                'is_seasonal': True,
                'target_url': '/criar',
            }

        # Verifica se há produtos cadastrados com estoque
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            prod = conn.execute('SELECT id, name, stock FROM products WHERE stock > 0 ORDER BY stock DESC LIMIT 1').fetchone()
            if prod:
                return {
                    'title': f"Destaque de Estoque: {prod['name']}",
                    'description': f"Produto com {prod['stock']} unidades disponíveis. Boa oportunidade para campanha de catálogo ou lifestyle.",
                    'recommended_pillar': 'Product Focus',
                    'is_seasonal': False,
                    'target_url': f"/criar?product_id={prod['id']}",
                }

        return {
            'title': 'Intenção antes da criação',
            'description': 'Explore novos pilares e conceitos para o universo da KIROS Aromas.',
            'recommended_pillar': 'Lifestyle',
            'is_seasonal': False,
            'target_url': '/criar',
        }

    def _build_proximo_passo(
        self,
        hoje: Dict[str, Any],
        criacao: Dict[str, Any],
        calendario: Dict[str, Any],
        aprendizados: Dict[str, Any],
    ) -> Dict[str, Any]:
        # 1. Se fila está pausada com jobs pendentes
        if hoje['queue_paused'] and hoje['pending_jobs'] > 0:
            return {
                'action_label': 'Retomar fila de geração',
                'description': f"Existem {hoje['pending_jobs']} tarefas aguardando na fila de execução pausada.",
                'url': '/conteudo',
                'priority': 'alta',
            }

        # 2. Se há campanha rascunho pendente de aprovação
        unapproved_campaigns = [c for c in criacao.get('recent_campaigns', []) if c.get('status') in ('draft', 'configured')]
        if unapproved_campaigns:
            top_camp = unapproved_campaigns[0]
            return {
                'action_label': f"Revisar storyboard de '{top_camp['title']}'",
                'description': 'A campanha está pronta para aprovação e estimativa de custos.',
                'url': top_camp['url'],
                'priority': 'alta',
            }

        # 3. Se há propostas de aprendizado pendentes
        if aprendizados.get('pending_proposals_count', 0) > 0:
            return {
                'action_label': 'Revisar sugestões de regras e preferências',
                'description': f"Existem {aprendizados['pending_proposals_count']} propostas de aprendizado aguardando aprovação.",
                'url': '/inicio#aprendizados',
                'priority': 'media',
            }

        # 4. Se não há posts agendados para a semana
        if calendario.get('scheduled_count', 0) == 0:
            return {
                'action_label': 'Planejar calendário editorial',
                'description': 'Nenhum post agendado no calendário. Revise suas campanhas aprovadas.',
                'url': '/calendario',
                'priority': 'media',
            }

        # 5. Passo padrão
        return {
            'action_label': 'Criar nova campanha',
            'description': 'Inicie um novo briefing estruturado a partir das ideias do Creative Director.',
            'url': '/criar',
            'priority': 'baixa',
        }

    def _build_calendario(self, now: datetime) -> Dict[str, Any]:
        scheduled_count = 0
        upcoming = []

        if self.calendar and hasattr(self.calendar, 'list_entries'):
            try:
                entries = self.calendar.list_entries()
                scheduled_count = len(entries)
                for e in entries[:3]:
                    upcoming.append({
                        'title': e.title,
                        'pillar': e.pillar,
                        'publish_time': e.scheduled_time or 'A definir',
                        'format': e.format_type,
                    })
            except Exception:
                pass

        return {
            'scheduled_count': scheduled_count,
            'upcoming_posts': upcoming,
            'weekly_saturation_alert': False,
        }

    def _build_criacao(self) -> Dict[str, Any]:
        recent = []
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT id, title, briefing_json, status, created_at FROM campaigns ORDER BY created_at DESC LIMIT 5').fetchall()
            for r in rows:
                slides_count = conn.execute('SELECT COUNT(*) FROM storyboard_slides WHERE campaign_id = ?', (r['id'],)).fetchone()[0]
                briefing = {}
                try:
                    briefing = json.loads(r['briefing_json']) if r['briefing_json'] else {}
                except Exception:
                    pass
                recent.append({
                    'id': r['id'],
                    'title': r['title'],
                    'objective': briefing.get('custom_objective', ''),
                    'status': r['status'],
                    'slides_count': slides_count,
                    'url': f"/conteudo?campaign_id={r['id']}",
                })

            pinned_count = 0
            total_ideas = 0
            try:
                pinned_count = conn.execute('SELECT COUNT(*) FROM idea_bank WHERE is_pinned = 1').fetchone()[0]
                total_ideas = conn.execute('SELECT COUNT(*) FROM idea_bank').fetchone()[0]
            except Exception:
                pass

        return {
            'recent_campaigns': recent,
            'pinned_ideas_count': pinned_count,
            'total_ideas_count': total_ideas,
        }

    def _build_aprendizados(self) -> Dict[str, Any]:
        if self.learning:
            sum_data = self.learning.summary()
            proposals = self.learning.list_proposals(status='suggested', limit=5)
            learnings = self.learning.list_learnings(limit=3)
            return {
                'total_corrections': sum_data.get('total_corrections', 0),
                'pending_proposals_count': sum_data.get('pending_proposals', 0),
                'approved_prompts_count': sum_data.get('approved_prompts', 0),
                'recent_proposals': proposals,
                'recent_learnings': learnings,
            }
        return {
            'total_corrections': 0,
            'pending_proposals_count': 0,
            'approved_prompts_count': 0,
            'recent_proposals': [],
            'recent_learnings': [],
        }
