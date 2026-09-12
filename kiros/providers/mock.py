class MockLLM:
    def complete(self, prompt: str) -> str:
        return 'Simulação local: nenhuma chamada de IA foi realizada.'


class MockVision:
    """Fixture de contrato: não interpreta pixels nem afirma atributos reais."""
    def analyze_product(self, photos):
        from kiros.library import PRODUCT_FIELDS
        return {'provider': 'mock', 'simulated': True,
                'attributes': {field: {'value': 'Não verificado — simulação local',
                                       'protection': 'critical' if field in ('label', 'logo') else 'protected'}
                               for field in PRODUCT_FIELDS}}

    def analyze_reference(self, photo):
        from kiros.library import VISUAL_FIELDS
        return {'provider': 'mock', 'simulated': True,
                'attributes': {field: None for field in VISUAL_FIELDS}}
