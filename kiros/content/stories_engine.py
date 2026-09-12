"""Motor de Planejamento e Sequência de Stories (Seção 38)."""
import uuid
from typing import Any, Dict, List, Optional

from kiros.content.models import (
    StorySequence,
    StoryFrame,
    VALID_STORY_TYPES,
    VALID_NARRATIVE_ROLES,
    VALID_INTERACTION_TYPES,
    ContentDomainError,
)


class StoriesEngine:
    """Planejador de Stories com narrativa sequencial própria (não é redimensionamento de feed)."""

    def plan_sequence(
        self,
        title: str,
        story_type: str = 'independent',
        objective: str = '',
        campaign_context: Optional[Dict[str, Any]] = None,
    ) -> StorySequence:
        """Cria uma sequência planejada de Stories (Seção 38).
        
        Planeja de 3 a 5 frames narrativos encadeados com papéis específicos:
        1. Gancho visual (hook)
        2. Contexto sensorial / matéria-prima (sensory_detail)
        3. Interação contextual autêntica (interaction)
        4. Fechamento suave com link na bio (closing)
        """
        if story_type not in VALID_STORY_TYPES:
            raise ContentDomainError(
                f"Tipo de Story inválido: '{story_type}'. Esperado: {VALID_STORY_TYPES}"
            )

        seq_id = f"seq-{uuid.uuid4().hex[:12]}"
        ctx = campaign_context or {}
        product_name = ctx.get('product_name') or 'Vela Aromática Artesanal'
        fragrance = ctx.get('fragrance') or 'Alecrim & Algodão'
        visual_tone = ctx.get('visual_tone') or 'luz matinal acolhedora em tons de madeira clara'

        frames = []

        # Frame 1: Gancho Visual (Hook)
        frames.append(StoryFrame(
            id=f"frame-{uuid.uuid4().hex[:12]}",
            sequence_id=seq_id,
            frame_order=1,
            narrative_role='hook',
            title='Abertura: O Ritual da Manhã',
            overlay_text=f'Um respiro bom para começar o dia.',
            visual_prompt=f'Vertical 9:16. Mesa de madeira clara banhada por luz de sol oblíqua da manhã, caneca de café fumegante e {product_name} acesa em primeiro plano com chama limpa. Composição editorial minimalista, textura orgânica, sem textos renderizados.',
            interaction_type='none',
            interaction_data={},
            interaction_justification='',
            caption_draft='Começar o dia com calma muda o ritmo de tudo.',
        ))

        # Frame 2: Detalhe Sensorial / Matéria-prima (Sensory Detail)
        frames.append(StoryFrame(
            id=f"frame-{uuid.uuid4().hex[:12]}",
            sequence_id=seq_id,
            frame_order=2,
            narrative_role='sensory_detail',
            title=f'Detalhe: Cera Vegetal e {fragrance}',
            overlay_text='Cera 100% vegetal de coco e pavio de puro algodão.',
            visual_prompt=f'Vertical 9:16. Macro close-up no copo âmbar da {product_name}, cera líquida dourada derretendo suavemente ao redor do pavio aceso, iluminação quente e foco seletivo nítido.',
            interaction_type='none',
            interaction_data={},
            interaction_justification='',
            caption_draft=f'Queima limpa e lenta, liberando as notas frescas de {fragrance.lower()} pelo ambiente.',
        ))

        # Frame 3: Interação Contextual Autêntica (Interaction)
        frames.append(StoryFrame(
            id=f"frame-{uuid.uuid4().hex[:12]}",
            sequence_id=seq_id,
            frame_order=3,
            narrative_role='interaction',
            title='Interação: Momento Preferido',
            overlay_text='Qual momento do dia pede uma vela acesa para você?',
            visual_prompt='Vertical 9:16. Vela aromática sobre livro de arte aberto em poltrona de linho cru, ambiente relaxante de final de tarde com sombras suaves.',
            interaction_type='poll',
            interaction_data={
                'question': 'Qual o seu ritual preferido?',
                'options': ['Café da manhã', 'Final da tarde'],
            },
            interaction_justification='Enquete autêntica sobre rotinas diárias com aromas, sem fórmulas forçadas de engajamento artificial.',
            caption_draft='Cada casa tem seu próprio ritmo de desacelerar.',
        ))

        # Frame 4: Fechamento Suave (Closing)
        frames.append(StoryFrame(
            id=f"frame-{uuid.uuid4().hex[:12]}",
            sequence_id=seq_id,
            frame_order=4,
            narrative_role='closing',
            title='Fechamento: Link da Bio',
            overlay_text=f'Descubra a coleção no link da bio.',
            visual_prompt=f'Vertical 9:16. Composição limpa com a embalagem artesanal e a {product_name} sobre bandeja de cerâmica esmaltada, luz de janela.',
            interaction_type='link_sticker',
            interaction_data={
                'text': 'Ver no catálogo',
                'url': ctx.get('destination_url') or 'https://instagram.com/kiros.sp',
            },
            interaction_justification='Sticker de link no frame final orientando quem deseja conhecer a coleção completa, sem pressão de venda agressiva.',
            caption_draft='Disponível no link da bio.',
        ))

        return StorySequence(
            id=seq_id,
            campaign_id=ctx.get('campaign_id'),
            title=title,
            story_type=story_type,
            objective=objective or 'Apresentação sensorial e conexão com a rotina do cliente',
            frames=frames,
            status='draft',
        )

    def validate_story_sequence(self, sequence: StorySequence) -> List[str]:
        """Verifica se a sequência de Stories atende aos critérios da Seção 38.
        
        - Não pode ser apenas 1 frame estático espelhado do feed.
        - Deve ter planejamento de sequência (mínimo de 3 frames).
        - Interações devem ser justificadas contextualmente.
        """
        issues = []
        if len(sequence.frames) < 3:
            issues.append(
                f"Sequência possui apenas {len(sequence.frames)} frame(s). "
                "Stories exigem planejamento de sequência próprio com um mínimo de 3 frames (Seção 38), "
                "e não um simples redimensionamento isolado do feed."
            )

        roles = [f.narrative_role for f in sequence.frames]
        if 'hook' not in roles:
            issues.append("Sequência de Stories não possui frame de abertura/gancho (hook).")

        for f in sequence.frames:
            if f.interaction_type != 'none' and not f.interaction_justification.strip():
                issues.append(
                    f"Frame {f.frame_order} possui interação '{f.interaction_type}' sem justificativa contextual. "
                    "Usar interações somente quando fizer sentido (Seção 38)."
                )

        return issues

