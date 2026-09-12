"""Command Bar com linguagem natural (Seção 57).

Princípios:
- Linguagem natural para navegação e comandos essenciais.
- Ações simples e reversíveis podem executar diretamente (ex: pausar geração).
- Ações que consomem créditos mostram impacto detalhado e não executam sem autorização.
- Publicação no Instagram exige confirmação explícita.
- Comandos ambíguos são explicitamente recusados.
"""
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from kiros.search import normalize_text, GlobalSearchService


@dataclass
class CommandResult:
    action_type: str
    message: str
    target_url: Optional[str] = None
    executed: bool = False
    reversible: bool = False
    requires_confirmation: bool = False
    impact: Optional[Dict[str, Any]] = None
    search_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_type': self.action_type,
            'message': self.message,
            'target_url': self.target_url,
            'executed': self.executed,
            'reversible': self.reversible,
            'requires_confirmation': self.requires_confirmation,
            'impact': self.impact,
            'search_results': self.search_results,
        }


PILLAR_MAP = {
    'lifestyle': ('lifestyle', 'Lifestyle'),
    'identidade': ('brand_identity', 'Brand Identity'),
    'brand identity': ('brand_identity', 'Brand Identity'),
    'embalagem': ('packaging', 'Packaging'),
    'packaging': ('packaging', 'Packaging'),
    'educacao': ('scent_education', 'Scent Education'),
    'scent education': ('scent_education', 'Scent Education'),
    'experiencia': ('fragrance_experience', 'Fragrance Experience'),
    'fragrance experience': ('fragrance_experience', 'Fragrance Experience'),
    'adjacencia': ('adjacency', 'Adjacency'),
    'adjacency': ('adjacency', 'Adjacency'),
}


class CommandBarService:
    """Interpreta comandos em linguagem natural e executa ações de acordo com a política de governança."""

    def __init__(
        self,
        database,
        campaigns,
        cost_manager,
        queue,
        idea_bank=None,
        search_service: Optional[GlobalSearchService] = None,
    ):
        self.db = database
        self.campaigns = campaigns
        self.cost_manager = cost_manager
        self.queue = queue
        self.idea_bank = idea_bank
        self.search = search_service or GlobalSearchService(database)

    def execute(self, text: str) -> CommandResult:
        raw_cmd = (text or '').strip()
        if not raw_cmd:
            return CommandResult(
                action_type='ambiguous_refusal',
                message='Nenhum comando digitado.',
                executed=False,
            )

        norm = normalize_text(raw_cmd)

        # 1. Recusa de comandos ambíguos para gastos/publicação (M11-A05 e Seção 56)
        ambiguous_terms = {'publicar', 'postar', 'gastar', 'executar', 'gerar', 'lancar', 'comprar', 'pagar', 'fazer tudo'}
        if norm in ambiguous_terms or norm.split() in [[t] for t in ambiguous_terms]:
            return CommandResult(
                action_type='ambiguous_refusal',
                message='Comando ambíguo recusado. Ações que envolvem gastos ou publicação exigem parâmetros específicos, transparência de impacto e confirmação explícita.',
                executed=False,
                requires_confirmation=True,
            )

        # 2. Publicação exige confirmação específica (M11-A03, Seção 57 e Seção 79)
        if any(term in norm for term in ('publicar campanha', 'postar no instagram', 'publicar post', 'agendar publicacao', 'publicar no feed', 'publicar stories')):
            return CommandResult(
                action_type='publish_confirmation_required',
                message='Publicação no Instagram não pode ser executada automaticamente via Command Bar. Exige auditoria prévia e confirmação explícita de operador humano na tela de publicação.',
                target_url='/calendario',
                executed=False,
                requires_confirmation=True,
            )

        # 3. Ações que consomem créditos: transparência de impacto sem execução direta (M11-A03)
        if any(term in norm for term in ('gerar imagem', 'gerar imagens', 'gerar slide', 'gerar slides', 'executar pipeline', 'regenerar slide', 'gerar versoes', 'executar campanha')):
            estimated = 0.15
            latest_cid = self._get_latest_campaign_id()
            if latest_cid:
                camp = self.campaigns.get_campaign(latest_cid)
                slides_count = len(camp.slides) if (camp and camp.slides) else 1
                estimated = slides_count * 0.15
            else:
                slides_count = 1

            return CommandResult(
                action_type='credit_impact_required',
                message=f'Esta ação consumirá créditos estimados em aproximadamente R$ {estimated:.2f} ({slides_count} slide{"s" if slides_count != 1 else ""}). É necessária aprovação explícita do plano antes de executar.',
                target_url=f'/conteudo?campaign_id={latest_cid}' if latest_cid else '/conteudo',
                executed=False,
                requires_confirmation=True,
                impact={
                    'estimated_cost': estimated,
                    'slides_count': slides_count,
                    'requires_approval': True,
                },
            )

        # 4. Ações simples e reversíveis: Pause / Resume da geração (executa diretamente)
        if any(term in norm for term in ('pause a geracao', 'pausar geracao', 'pausar fila', 'pause fila', 'parar geracao')):
            if self.queue:
                self.queue.pause()
            return CommandResult(
                action_type='reversible_action',
                message='Geração pausada com sucesso. Resultados já concluídos foram preservados.',
                executed=True,
                reversible=True,
                target_url='/conteudo',
            )

        if any(term in norm for term in ('retome a geracao', 'retomar geracao', 'despausar fila', 'continuar geracao')):
            if self.queue:
                self.queue.resume()
            return CommandResult(
                action_type='reversible_action',
                message='Geração retomada com sucesso.',
                executed=True,
                reversible=True,
                target_url='/conteudo',
            )

        # 5. Consulta de custo: "Quanto esta campanha vai custar?"
        if any(term in norm for term in ('quanto esta campanha vai custar', 'quanto essa campanha vai custar', 'quanto vai custar', 'qual o custo da campanha', 'qual o custo')):
            latest_cid = self._get_latest_campaign_id()
            if not latest_cid:
                return CommandResult(
                    action_type='info',
                    message='Nenhuma campanha encontrada no momento. Estimativa base por slide é de R$ 0.15. Nenhum crédito foi consumido por esta consulta.',
                    executed=True,
                    impact={'estimated_cost': 0.0, 'actual_cost': 0.0},
                )
            try:
                camp = self.campaigns.get_campaign(latest_cid)
                if not camp:
                    return CommandResult(action_type='info', message='Campanha não encontrada.', executed=True)
                slides = camp.slides or []
                est_cost = len(slides) * 0.15
                with sqlite3.connect(self.db.path) as conn:
                    spent_row = conn.execute("SELECT COALESCE(SUM(actual_cost), 0.0) FROM cost_records WHERE campaign_id=?", (latest_cid,)).fetchone()
                    spent = float(spent_row[0]) if spent_row else 0.0
                msg = (
                    f"Campanha '{camp.title}': Estimativa total de R$ {est_cost:.2f} "
                    f"para {len(slides)} slides. Total já realizado: R$ {spent:.2f}. "
                    "Nenhum crédito foi consumido por esta consulta."
                )
                return CommandResult(
                    action_type='info',
                    message=msg,
                    target_url=f"/conteudo?campaign_id={latest_cid}",
                    executed=True,
                    impact={'estimated_cost': est_cost, 'actual_cost': spent},
                )
            except Exception as exc:
                return CommandResult(
                    action_type='info',
                    message=f'Erro ao consultar estimativa: {str(exc)}',
                    executed=True,
                )

        # 6. Comparar versões: "Compare as três últimas versões"
        if any(term in norm for term in ('compare as tres ultimas versoes', 'comparar ultimas versoes', 'comparar versoes', 'compare as 3 ultimas versoes', 'comparar 3 versoes')):
            latest_cid = self._get_latest_campaign_id()
            if not latest_cid:
                return CommandResult(
                    action_type='info',
                    message='Nenhuma campanha com versões disponível para comparação.',
                    executed=True,
                )
            return CommandResult(
                action_type='navigate',
                message='Comparando as versões mais recentes geradas.',
                target_url=f"/conteudo?campaign_id={latest_cid}&tab=compare",
                executed=True,
            )

        # 7. "Abra a última campanha"
        if any(term in norm for term in ('abra a ultima campanha', 'abrir ultima campanha', 'abrir a ultima campanha', 'ver ultima campanha', 'ultima campanha')):
            latest_cid = self._get_latest_campaign_id()
            if not latest_cid:
                return CommandResult(
                    action_type='info',
                    message='Nenhuma campanha cadastrada no estúdio.',
                    executed=True,
                    target_url='/conteudo',
                )
            title = self._get_campaign_title(latest_cid)
            return CommandResult(
                action_type='navigate',
                message=f"Abrindo última campanha: '{title}'",
                target_url=f"/conteudo?campaign_id={latest_cid}",
                executed=True,
            )

        # 8. "Mostre minhas ideias de Lifestyle" (ou outro pilar)
        match_ideas = re.search(r'mostr(?:e|ar) (?:minhas )?ideias? d[eo] ([a-z0-9_ -]+)', norm)
        if not match_ideas:
            match_ideas = re.search(r'ver ideias? d[eo] ([a-z0-9_ -]+)', norm)
        if match_ideas:
            pillar_term = match_ideas.group(1).strip()
            pillar_key = None
            pillar_name = pillar_term.capitalize()
            for key, (slug, name) in PILLAR_MAP.items():
                if key in pillar_term or pillar_term in key:
                    pillar_key = slug
                    pillar_name = name
                    break
            target = f"/criar?pillar={pillar_key}" if pillar_key else "/criar"
            return CommandResult(
                action_type='navigate',
                message=f"Mostrando ideias do pilar '{pillar_name}'",
                target_url=target,
                executed=True,
            )

        # 9. Navegação direta para seções principais
        if any(term in norm for term in ('ir para calendario', 'abrir calendario', 'ver calendario')):
            return CommandResult(action_type='navigate', message='Abrindo Calendário', target_url='/calendario', executed=True)
        if any(term in norm for term in ('ir para biblioteca', 'abrir biblioteca', 'ver biblioteca')):
            return CommandResult(action_type='navigate', message='Abrindo Biblioteca', target_url='/biblioteca', executed=True)
        if any(term in norm for term in ('ir para configuracoes', 'abrir configuracoes', 'ver configuracoes')):
            return CommandResult(action_type='navigate', message='Abrindo Configurações', target_url='/configuracoes', executed=True)
        if any(term in norm for term in ('ir para insights', 'abrir insights', 'ver insights')):
            return CommandResult(action_type='navigate', message='Abrindo Insights', target_url='/insights', executed=True)
        if any(term in norm for term in ('ir para marca', 'abrir marca', 'ver marca')):
            return CommandResult(action_type='navigate', message='Abrindo Marca', target_url='/marca', executed=True)
        if any(term in norm for term in ('ir para inicio', 'abrir inicio', 'ver dashboard', 'abrir dashboard')):
            return CommandResult(action_type='navigate', message='Abrindo Início', target_url='/inicio', executed=True)
        if any(term in norm for term in ('ir para criar', 'abrir criar', 'criar campanha')):
            return CommandResult(action_type='navigate', message='Abrindo Criar', target_url='/criar', executed=True)
        if any(term in norm for term in ('ir para conteudo', 'abrir conteudo', 'ver campanhas')):
            return CommandResult(action_type='navigate', message='Abrindo Conteúdo', target_url='/conteudo', executed=True)

        # 10. Fallback: Executa busca global se não for comando operacional explícito
        search_results = self.search.search(raw_cmd, limit=10)
        if search_results:
            return CommandResult(
                action_type='search_fallback',
                message=f"Encontrados {len(search_results)} resultados para '{raw_cmd}'",
                search_results=[r.to_dict() for r in search_results],
                executed=True,
                target_url=f"/biblioteca?q={raw_cmd}",
            )

        return CommandResult(
            action_type='info',
            message=f"Comando não reconhecido: '{raw_cmd}'. Tente 'Abra a última campanha', 'Pause a geração' ou busque por produtos/ideias.",
            executed=False,
        )

    def _get_latest_campaign_id(self) -> Optional[str]:
        with sqlite3.connect(self.db.path) as conn:
            row = conn.execute('SELECT id FROM campaigns ORDER BY created_at DESC LIMIT 1').fetchone()
            return row[0] if row else None

    def _get_campaign_title(self, campaign_id: str) -> str:
        with sqlite3.connect(self.db.path) as conn:
            row = conn.execute('SELECT title FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
            return row[0] if row else campaign_id
