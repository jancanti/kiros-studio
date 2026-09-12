"""Testes de Stories e Planejamento de Sequência Narrativa Própria (Seção 38 e M08-A04)."""
import unittest

from kiros.content.stories_engine import StoriesEngine
from kiros.content.models import StorySequence, StoryFrame, ContentDomainError


class StoriesEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = StoriesEngine()

    def test_independent_story_sequence_planning(self):
        """M08-A04: Stories independentes têm planejamento de sequência próprio (3 a 5 frames narrativos)."""
        seq = self.engine.plan_sequence(
            title="Um Dia no Ateliê",
            story_type="independent",
            objective="Engajamento sensorial com o processo artesanal",
            campaign_context={
                'product_name': 'Vela Botânica de Laranja Doce',
                'fragrance': 'Laranja Doce & Cedro',
                'visual_tone': 'Luz natural e cerâmica rústica',
            },
        )

        self.assertEqual(seq.story_type, "independent")
        self.assertEqual(seq.title, "Um Dia no Ateliê")
        self.assertGreaterEqual(len(seq.frames), 3)
        self.assertLessEqual(len(seq.frames), 5)

        roles = [f.narrative_role for f in seq.frames]
        # Deve conter abertura, detalhe sensorial, interação e fechamento
        self.assertIn('hook', roles)
        self.assertIn('sensory_detail', roles)
        self.assertIn('interaction', roles)
        self.assertIn('closing', roles)

        # Validação de conformidade passa sem erros
        issues = self.engine.validate_story_sequence(seq)
        self.assertEqual(issues, [])

    def test_derived_from_campaign_story_planning_not_just_feed_resize(self):
        """M08-A04: Stories derivados de campanha não são mero redimensionamento do feed."""
        seq = self.engine.plan_sequence(
            title="Lançamento Alecrim Outono",
            story_type="derived_from_campaign",
            objective="Apresentação da coleção para seguidores",
            campaign_context={
                'campaign_id': 'camp-12345',
                'product_name': 'Vela Alecrim & Algodão',
                'fragrance': 'Alecrim',
                'destination_url': 'https://instagram.com/usekiros',
            },
        )

        self.assertEqual(seq.story_type, "derived_from_campaign")
        self.assertEqual(seq.campaign_id, 'camp-12345')

        # Cada frame possui composição visual vertical 9:16 própria e texto conciso de tela
        for f in seq.frames:
            self.assertTrue(f.visual_prompt.startswith('Vertical 9:16'))
            self.assertTrue(len(f.overlay_text) > 0)
            self.assertNotIn('#', f.overlay_text)

        # Não é apenas 1 frame estático
        self.assertTrue(len(seq.frames) >= 4)

    def test_rejection_of_single_frame_feed_resize(self):
        """M08-A04: Rejeita sequência simplista de apenas 1 frame (mero espelhamento de feed)."""
        single_frame_seq = StorySequence(
            id="seq-invalid",
            campaign_id="camp-1",
            title="Feed Redimensionado",
            story_type="derived_from_campaign",
            frames=[
                StoryFrame(
                    id="f1",
                    sequence_id="seq-invalid",
                    frame_order=1,
                    narrative_role="hook",
                    title="Feed em 9:16",
                    overlay_text="Vela aromática",
                    visual_prompt="Mesmo post do feed esticado para vertical",
                )
            ],
        )

        issues = self.engine.validate_story_sequence(single_frame_seq)
        self.assertTrue(any('mínimo de 3 frames' in issue.lower() for issue in issues))

    def test_contextual_interactions_require_justification(self):
        """M08-A04: Usar interações somente quando fizer sentido e com justificativa contextual (Seção 38)."""
        seq = self.engine.plan_sequence(
            title="Interações Aromáticas",
            story_type="independent",
        )

        # Na sequência planejada, frames com interação possuem justificativa
        interaction_frames = [f for f in seq.frames if f.interaction_type != 'none']
        self.assertTrue(len(interaction_frames) > 0)
        for f in interaction_frames:
            self.assertTrue(len(f.interaction_justification.strip()) > 0)

        # Se criarmos uma interação vazia sem justificativa -> Validação detecta e alerta
        unjustified_seq = StorySequence(
            id="seq-unjustified",
            campaign_id="camp-1",
            title="Interação Gratuita",
            story_type="independent",
            frames=[
                StoryFrame(id="f1", sequence_id="seq-u", frame_order=1, narrative_role="hook", title="F1", overlay_text="T1", visual_prompt="P1"),
                StoryFrame(id="f2", sequence_id="seq-u", frame_order=2, narrative_role="context", title="F2", overlay_text="T2", visual_prompt="P2"),
                StoryFrame(id="f3", sequence_id="seq-u", frame_order=3, narrative_role="interaction", title="F3", overlay_text="T3", visual_prompt="P3",
                           interaction_type="poll", interaction_justification=""),
            ],
        )
        issues = self.engine.validate_story_sequence(unjustified_seq)
        self.assertTrue(any('sem justificativa contextual' in issue.lower() for issue in issues))


if __name__ == '__main__':
    unittest.main()

