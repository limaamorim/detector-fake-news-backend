"""
Service de integração com a IA via OpenRouter.

Responsabilidade única: enviar texto para o modelo configurado
e retornar os metadados semânticos extraídos (sensacionalismo,
evidências, resumo e afirmações principais).

A IA NÃO define o score final. Ela apenas auxilia na interpretação
do conteúdo, retornando sinais que o scoring_service usará.
"""

import json
import logging
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from app.models.schemas import AIAnalysis

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração via variáveis de ambiente (nunca hardcoded)
# ---------------------------------------------------------------------------
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Timeout para chamadas à IA (segundos)
_AI_TIMEOUT = 30

# Valores padrão usados se a IA retornar resposta inválida
_FALLBACK_ANALISE = AIAnalysis(
    sensacionalismo=50,
    evidencia=50,
    resumo="Não foi possível obter análise detalhada da IA.",
    afirmacoes=[],
)

_PROMPT_SISTEMA = """Você é um analisador de texto objetivo e imparcial.
Retorne APENAS JSON válido, sem markdown, sem explicações, sem código fence.
Nunca afirme que algo é verdadeiro ou falso."""

_PROMPT_USUARIO = """
Analise o texto abaixo.

IMPORTANTE:

- NÃO determine se é verdadeiro ou falso.
- NÃO faça fact-checking completo.
- Avalie apenas os sinais presentes no texto.

Regras específicas para imagens/OCR (muito importante):
- Erros comuns de OCR (troca de letras, acentos, palavras parcialmente ilegíveis) NÃO devem reduzir evidência ou credibilidade.
- A ausência de autor, data ou fonte no texto NÃO deve ser interpretada como desinformação.
- Se o texto parecer uma manchete simples e plausível (sem alegações extraordinárias), atribua evidência moderada (40-60) mesmo sem fonte.

Ao calcular EVIDÊNCIA considere:


1. Presença de fontes.
2. Presença de dados.
3. Presença de estudos citados.
4. Compatibilidade com conhecimento amplamente aceito.
5. Plausibilidade da afirmação.

Exemplos:

"Beber água ajuda na hidratação."
→ evidência alta

"Vacinas causam chips de rastreamento."
→ evidência muito baixa

"Terremoto destruirá o Brasil amanhã."
→ evidência muito baixa

Retorne apenas JSON:

{
  "sensacionalismo": 0,
  "evidencia": 0,
  "resumo": "",
  "afirmacoes": []
}

Sensacionalismo:
0 = neutro
100 = extremamente alarmista

Ao calcular evidência considere:

- presença de fontes
- presença de estudos
- presença de especialistas
- compatibilidade com conhecimento científico conhecido
- plausibilidade da afirmação

IMPORTANTE:

Não considere ausência de fonte como evidência de falsidade.

Se o texto fizer uma afirmação plausível e comum
(ex.: beber água faz bem, exercício melhora saúde,
alimentação saudável ajuda no emagrecimento),
atribua evidência moderada (40-60) mesmo sem fontes explícitas.

Uma afirmação plausível não deve receber nota muito baixa apenas por ausência de fonte na imagem.

Evidência:
0 = afirmação sem base plausível
25 = muito fraca
50 = plausível mas sem comprovação apresentada
75 = plausível com indícios ou referências
100 = forte embasamento e fontes verificáveis

Texto:
"""


async def analisar_texto_com_ia(texto: str) -> AIAnalysis:
    """
    Envia texto para o modelo de IA e retorna a análise semântica.

    Em caso de falha na API ou resposta malformada, retorna valores
    neutros padrão para não bloquear o fluxo de scoring.

    Args:
        texto: Texto limpo e truncado para análise.

    Returns:
        AIAnalysis com sensacionalismo, evidência, resumo e afirmações.
    """
    if not _OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY não configurada.")
        return _FALLBACK_ANALISE

    payload = {
        "model": _OPENROUTER_MODEL,
        "max_tokens": 1000,
        "temperature": 0.1,  # Baixa temperatura para respostas mais determinísticas
        "messages": [
            {"role": "system", "content": _PROMPT_SISTEMA},
            {"role": "user", "content": f"{_PROMPT_USUARIO}{texto}"},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=_AI_TIMEOUT) as client:
            response = await client.post(
                _OPENROUTER_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {_OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://fakecheck.ai",
                    "X-Title": "FakeCheck AI",
                },
            )
            response.raise_for_status()

        dados = response.json()
        conteudo_raw = dados["choices"][0]["message"]["content"]

        return _parsear_resposta_ia(conteudo_raw)

    except httpx.HTTPStatusError as e:
        logger.error("Erro HTTP na API OpenRouter: %s", str(e))
        return _FALLBACK_ANALISE
    except httpx.TimeoutException:
        logger.error("Timeout na chamada à IA após %ds.", _AI_TIMEOUT)
        return _FALLBACK_ANALISE
    except Exception as e:
        logger.error("Erro inesperado na chamada à IA: %s", str(e))
        return _FALLBACK_ANALISE


def _parsear_resposta_ia(conteudo: str) -> AIAnalysis:
    """
    Tenta parsear o JSON retornado pela IA com tolerância a erros.

    Estratégia:
    1. Parse direto do conteúdo.
    2. Extração de JSON via regex (caso tenha texto extra ao redor).
    3. Fallback com valores neutros.

    Args:
        conteudo: String bruta retornada pelo modelo.

    Returns:
        AIAnalysis com os campos parseados.
    """
    # Tentativa 1: parse direto
    try:
        dados = json.loads(conteudo.strip())
        return _mapear_para_ai_analysis(dados)
    except json.JSONDecodeError:
        pass

    # Tentativa 2: extração via regex (ignora texto ao redor do JSON)
    try:
        match = re.search(r"\{.*\}", conteudo, re.DOTALL)
        if match:
            dados = json.loads(match.group())
            return _mapear_para_ai_analysis(dados)
    except (json.JSONDecodeError, AttributeError):
        pass

    logger.warning("IA retornou resposta não parseável. Usando fallback.")
    return _FALLBACK_ANALISE


def _mapear_para_ai_analysis(dados: dict[str, Any]) -> AIAnalysis:
    """
    Mapeia um dicionário para o schema AIAnalysis com validação de ranges.

    Garante que valores numéricos estejam entre 0 e 100 mesmo se a IA
    retornar valores fora do esperado.

    Args:
        dados: Dicionário já parseado do JSON.

    Returns:
        AIAnalysis validado.
    """
    def clamp(v: Any, default: int = 50) -> int:
        """Garante valor entre 0 e 100."""
        try:
            return max(0, min(100, int(v)))
        except (TypeError, ValueError):
            return default

    return AIAnalysis(
        sensacionalismo=clamp(dados.get("sensacionalismo")),
        evidencia=clamp(dados.get("evidencia")),
        resumo=str(dados.get("resumo", "Resumo não disponível"))[:1000],
        afirmacoes=[
            str(a) for a in dados.get("afirmacoes", []) if isinstance(a, str)
        ][:5],  # Limita a 5 afirmações
    )
