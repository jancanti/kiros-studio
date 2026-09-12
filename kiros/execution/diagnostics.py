"""Diagnóstico e categorização estruturada de falhas na geração (Seção 69)."""
from typing import Optional

from kiros.execution.models import FailureDiagnostic


def analyze_execution_failure(
    provider_id: str,
    step_name: str,
    error_message: str,
    estimated_cost: float,
    status_code: Optional[int] = None,
) -> FailureDiagnostic:
    """Analisa o erro ocorrido e gera diagnóstico com provedor, etapa, causa provável, sugestão de correção e custo potencial."""
    msg = (error_message or '').lower()
    prov = provider_id.upper()
    cost = float(estimated_cost or 0.0)

    # 1. Rate Limit / Quota Exceeded
    if 'rate limit' in msg or '429' in msg or 'quota' in msg or status_code == 429:
        cause = f"Limite de requisições por minuto atingido no provedor {prov}."
        fix = "Aguarde a liberação da janela de taxa (60s) ou alterne para um motor alternativo com maior cota (ex: Fast)."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=cost,
        )

    # 2. Timeout / Rede / Conexão Incerta
    if 'timeout' in msg or 'tempo limite' in msg or '504' in msg or status_code == 504:
        cause = f"Tempo limite de conexão excedido ao aguardar resposta do provedor {prov}."
        fix = "Reconcilie o status da requisição antes de nova tentativa para evitar cobrança duplicada. Se persistir, reduza a complexidade do prompt."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=cost,
        )

    # 3. Moderação / Filtro de Segurança / Políticas de Conteúdo
    if 'safety' in msg or 'moderation' in msg or 'filter' in msg or 'policy' in msg or 'bloqueio' in msg:
        cause = f"O prompt ou composição do slide acionou filtros de segurança ou moderação do {prov}."
        fix = "Revise o prompt visual do slide, removendo termos ambíguos ou descrições que possam ser interpretadas como não conformes."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=0.0,
        )

    # 4. Orçamento / Budget Exceeded
    if 'budget' in msg or 'orçamento' in msg or 'limite' in msg:
        cause = "Limite de orçamento planejado para a campanha foi atingido."
        fix = "Ajuste o limite de orçamento da campanha em Configurações ou selecione motores mais econômicos para os slides restantes."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=cost,
        )

    # 5. Autenticação / Chave Inválida / Secret
    if 'auth' in msg or 'unauthorized' in msg or '401' in msg or '403' in msg or 'key' in msg or status_code in (401, 403):
        cause = f"Credencial ou chave de API rejeitada pelo provedor {prov}."
        fix = "Verifique e atualize a chave de API do provedor em Configurações > Provedores antes de reexecutar."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=0.0,
        )

    # 6. Modo Mock / Recusa de Egress Central
    if 'mock' in msg or 'egress' in msg or 'regras de ambiente' in msg:
        cause = "Ambiente configurado em modo mock estrito; tráfego externo real foi recusado pelo gateway."
        fix = "Em ambiente de desenvolvimento e testes, utilize mocks determinísticos conforme as diretrizes do projeto."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=0.0,
        )

    # 7. Erro Genérico do Provedor / Servidor Indisponível (500, 502, 503)
    if '500' in msg or '502' in msg or '503' in msg or status_code in (500, 502, 503):
        cause = f"Instabilidade temporária nos servidores do provedor {prov}."
        fix = "Aguarde alguns minutos para nova tentativa automática conforme política finita de retries, ou alterne o motor do slide."
        return FailureDiagnostic(
            provider=prov,
            step=step_name,
            probable_cause=cause,
            suggested_fix=fix,
            potential_cost=cost,
        )

    # Fallback geral
    cause = f"Erro inesperado durante a execução da etapa: {error_message[:120]}"
    fix = "Verifique os parâmetros da etapa no pipeline e tente novamente."
    return FailureDiagnostic(
        provider=prov,
        step=step_name,
        probable_cause=cause,
        suggested_fix=fix,
        potential_cost=cost,
    )

