"""Fixtures de contrato para checagem de fidelidade de produto (M06-A05).

Aviso: Fixtures sintéticas determinísticas utilizadas exclusivamente para validação de
contratos e fluxos de governança. Não constituem acurácia real de visão computacional.
"""
from typing import Any, Dict


# Fixture de Produto Correto: Todas as dimensões coincidem com a referência e Product Bible
FIXTURE_CORRECT_PRODUCT: Dict[str, Any] = {
    'shape': {'detected': 'Cilíndrico clássico', 'score': 95.0, 'status': 'match'},
    'proportion': {'detected': '1:1.5 padrão', 'score': 95.0, 'status': 'match'},
    'cap': {'detected': 'Tampa de madeira torneada escura', 'score': 95.0, 'status': 'match'},
    'label': {'detected': 'Papel linho branco com tipografia preta serifada', 'score': 95.0, 'status': 'match'},
    'logo': {'detected': 'Monograma Kiros centralizado na parte superior', 'score': 95.0, 'status': 'match'},
    'colors': {'detected': 'Frasco âmbar e madeira nobre', 'score': 92.0, 'status': 'match'},
    'material': {'detected': 'Vidro espesso âmbar e madeira natural', 'score': 93.0, 'status': 'match'},
}

# Fixture de Produto Alterado: Mudanças na forma, proporção e materiais
FIXTURE_ALTERED_PRODUCT: Dict[str, Any] = {
    'shape': {'detected': 'Frasco quadrado contemporâneo', 'score': 40.0, 'status': 'divergent',
              'discrepancy': 'Forma quadrada identificada quando o produto original possui silhueta cilíndrica.'},
    'proportion': {'detected': '1:2.4 alongado', 'score': 50.0, 'status': 'divergent',
                   'discrepancy': 'Proporção excessivamente alongada em relação à referência oficial.'},
    'cap': {'detected': 'Tampa metálica rosqueada', 'score': 45.0, 'status': 'divergent',
            'discrepancy': 'Tampa metálica divergente da madeira torneada prescrita.'},
    'label': {'detected': 'Papel linho branco', 'score': 90.0, 'status': 'match'},
    'logo': {'detected': 'Monograma Kiros', 'score': 90.0, 'status': 'match'},
    'colors': {'detected': 'Vidro incolor transparente', 'score': 55.0, 'status': 'divergent',
               'discrepancy': 'Coloração incolor divergente do tom âmbar original.'},
    'material': {'detected': 'Acrílico e alumínio', 'score': 45.0, 'status': 'divergent',
                 'discrepancy': 'Materiais plásticos/metálicos detectados no lugar de vidro e madeira.'},
}

# Fixture de Etiqueta Alterada: Forma correta porém etiqueta descaracterizada ou ausente
FIXTURE_ALTERED_LABEL: Dict[str, Any] = {
    'shape': {'detected': 'Cilíndrico clássico', 'score': 95.0, 'status': 'match'},
    'proportion': {'detected': '1:1.5 padrão', 'score': 95.0, 'status': 'match'},
    'cap': {'detected': 'Tampa de madeira torneada escura', 'score': 95.0, 'status': 'match'},
    'label': {'detected': 'Etiqueta plástica adesiva transparente ou ilegível', 'score': 25.0, 'status': 'divergent',
              'discrepancy': 'Etiqueta em material incorreto ou texto ilegível, divergente do papel linho oficial.'},
    'logo': {'detected': 'Monograma presente porém deslocado', 'score': 70.0, 'status': 'divergent',
             'discrepancy': 'Logo descentralizado ou parcialmente cortado.'},
    'colors': {'detected': 'Frasco âmbar e madeira', 'score': 92.0, 'status': 'match'},
    'material': {'detected': 'Vidro espesso âmbar', 'score': 92.0, 'status': 'match'},
}

# Fixture de Logo Alterado: Frasco e etiqueta corretos porém logo adulterado ou substituído
FIXTURE_ALTERED_LOGO: Dict[str, Any] = {
    'shape': {'detected': 'Cilíndrico clássico', 'score': 95.0, 'status': 'match'},
    'proportion': {'detected': '1:1.5 padrão', 'score': 95.0, 'status': 'match'},
    'cap': {'detected': 'Tampa de madeira torneada escura', 'score': 95.0, 'status': 'match'},
    'label': {'detected': 'Papel linho branco', 'score': 90.0, 'status': 'match'},
    'logo': {'detected': 'Símbolo genérico abstrato ou logo ausente', 'score': 15.0, 'status': 'missing',
             'discrepancy': 'Atributo crítico: Monograma oficial da marca ausente ou substituído por gráfico genérico.'},
    'colors': {'detected': 'Frasco âmbar e madeira', 'score': 92.0, 'status': 'match'},
    'material': {'detected': 'Vidro espesso âmbar', 'score': 92.0, 'status': 'match'},
}

