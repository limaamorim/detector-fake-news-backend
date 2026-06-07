"""
Service de cálculo do score de confiabilidade.

Este é o coração do sistema: toda a pontuação final é determinada
por regras objetivas do backend. A IA apenas fornece sinais auxiliares
(sensacionalismo e nível de evidência), mas NÃO define a nota.

Fórmula de pontuação (total: 100 pontos):
    - Credibilidade da fonte:    até 40 pontos
    - Autor identificado:            10 pontos
    - Data identificada:              5 pontos
    - Referências detectadas:        15 pontos
    - Evidências (sinal da IA):      20 pontos
    - Ausência de sensacionalismo:   10 pontos
"""

import logging
from dataclasses import dataclass, field

from app.models.schemas import (
    AIAnalysis,
    AnalysisResponse,
    ExtractedContent,
    FonteInfo,
    Indicadores,
)
from app.utils.helpers import classificar_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classificação de domínios por credibilidade
# ---------------------------------------------------------------------------

_DOMINIOS_ALTA_CONFIANCA = {
    "gov.br", "edu.br", "who.int", "nih.gov",
    "scielo.br", "fiocruz.br", "ibge.gov.br",
    "inpe.br", "anvisa.gov.br", "mec.gov.br",
}

_DOMINIOS_MEDIA_CONFIANCA = {
    "g1.globo.com", "uol.com.br", "cnn.com", "bbc.com",
    "folha.uol.com.br", "estadao.com.br", "valor.com.br",
    "reuters.com", "apnews.com", "agenciabrasil.ebc.com.br",
    "agencialupa.org",
"aosfatos.org",
}

# Scores de credibilidade de fonte (usados para calcular até 40 pontos)
_SCORE_ALTA = 40
_SCORE_MEDIA = 25
_SCORE_BAIXA = 10


@dataclass
class _PontosDetalhe:
    """Estrutura interna para acumular pontos e justificativas."""

    score_fonte: int = 0
    score_autor: int = 0
    score_data: int = 0
    score_referencias: int = 0
    score_evidencias: int = 0
    score_sensacionalismo: int = 0
    credibilidade_fonte: int = 0
    positivos: list[str] = field(default_factory=list)
    atencao: list[str] = field(default_factory=list)
    inconsistencias: list[str] = field(default_factory=list)


def calcular_score_url(
    conteudo: ExtractedContent,
    analise_ia: AIAnalysis,
) -> AnalysisResponse:
    """
    Calcula o score de confiabilidade para análise de URL.

    Aplica todas as regras de pontuação do backend sobre os dados
    extraídos e os sinais fornecidos pela IA.

    Args:
        conteudo: Conteúdo estruturado extraído da URL.
        analise_ia: Resultado semântico fornecido pela IA.

    Returns:
        AnalysisResponse completo com score, classificação e justificativas.
    """
    pontos = _PontosDetalhe()

    # --- 1. Credibilidade da fonte (até 40 pts) ---
    pontos.score_fonte, pontos.credibilidade_fonte = _avaliar_fonte(
        conteudo.dominio, pontos
        
    )

    # --- 2. Autor (10 pts) ---
    if conteudo.autor:
        pontos.score_autor = 10
        pontos.positivos.append(f"Autor identificado: {conteudo.autor}")
    else:
        pontos.atencao.append("Autor não identificado.")

    # --- 3. Data (5 pts) ---
    if conteudo.data:
        pontos.score_data = 5
        pontos.positivos.append(f"Data de publicação disponível: {conteudo.data}")
    else:
        pontos.atencao.append("Data de publicação não encontrada.")

    # --- 4. Referências externas (15 pts) ---
    if conteudo.tem_referencias:
        pontos.score_referencias = 15
        pontos.positivos.append("Texto contém referências ou fontes externas.")
    else:
        pontos.score_referencias = 5
        pontos.atencao.append("Poucas referência externa identificada.")

    # --- 5. Penalidade texto curto ---
    if conteudo.contagem_palavras < 100:
        pontos.atencao.append(
            f"Texto curto ({conteudo.contagem_palavras} palavras) — "
            "análise com menor precisão."
        )
        pontos.score_fonte = max(0, pontos.score_fonte - 10)

    # --- 6. Evidências (sinal da IA, até 20 pts) ---
    pontos.score_evidencias = _calcular_pontos_evidencia(
        analise_ia.evidencia, pontos
    )

    

    # --- 7. Sensacionalismo (sinal da IA, até 10 pts) ---
    pontos.score_sensacionalismo = _calcular_pontos_sensacionalismo(
        analise_ia.sensacionalismo, pontos
    )

    score_total = _somar_score(pontos)

    score_total = max(0, min(100, score_total))

    return _montar_resposta(
        score=score_total,
        tipo="url",
        titulo=conteudo.titulo,
        resumo=analise_ia.resumo,
        dominio=conteudo.dominio,
        credibilidade_fonte=pontos.credibilidade_fonte,
        analise_ia=analise_ia,
        pontos=pontos,
    )


def calcular_score_imagem(analise_ia: AIAnalysis) -> AnalysisResponse:
    """Calcula o score de confiabilidade para análise de imagem.

    Regras (para evitar falsos positivos em manchetes simples):
    - ausência de autor/data/fonte NÃO deve derrubar score;
    - imagens começam com um baseline neutro e ajustam apenas por
      sinais semânticos (evidência e sensacionalismo);
    - classificação "Possível Desinformação" deve depender de sinais
      realmente ruins (ex.: baixo nível de evidência + alto sensacionalismo,
      ou ausência de plausibilidade detectada).
    """

    pontos = _PontosDetalhe()

    # Baseline: imagens sem metadados não são automaticamente "baixas".
    # Usamos credibilidade_fonte como indicativo de "verificabilidade"
    # (não como penalidade) e iniciamos o score com um valor neutro.
    pontos.credibilidade_fonte = 55
    pontos.atencao.append(
        "A imagem não possui metadados suficientes para verificar fonte, autor ou data."
    )
    pontos.positivos.append(
        "Avaliação baseada no conteúdo textual extraído via OCR (sem inferir falsidade por ausência de fonte)."
    )

    # Evidências e sensacionalismo via sinais da IA
    # (esses valores já carregam a lógica de plausibilidade/sensatez do modelo).
    pontos.score_evidencias = _calcular_pontos_evidencia(analise_ia.evidencia, pontos)
    pontos.score_sensacionalismo = _calcular_pontos_sensacionalismo(
        analise_ia.sensacionalismo, pontos
    )

    # Ajustes finos para manchetes simples
    # Se o modelo entender como plausível/normal (evidência moderada),
    # evitamos derrubar abaixo de ~50.
    baseline = 50
    if analise_ia.evidencia >= 40 and analise_ia.sensacionalismo <= 60:
        baseline += 5
        pontos.positivos.append(
            "Conteúdo com tom informativo e afirmações plausíveis (sem sinais fortes de apelo emocional)."
        )

    # Se houver muito sensacionalismo + pouca evidência, sinalizamos possível desinformação.
    # Isso substitui penalidades por ausência de fonte.
    penalty_extra = 0
    if analise_ia.evidencia <= 25 and analise_ia.sensacionalismo >= 70:
        penalty_extra = 20
        pontos.inconsistencias.append(
            "Baixo embasamento semântico combinado com alto sensacionalismo." 
        )

    # Componentes do _somar_score seriam pequenos; então calculamos score total
    # usando baseline + componentes semânticos.
    score_total = baseline + pontos.score_evidencias + pontos.score_sensacionalismo - penalty_extra
    score_total = max(0, min(100, score_total))

    return _montar_resposta(

        score=score_total,
        tipo="image",
        titulo=None,
        resumo=analise_ia.resumo,
        dominio="imagem",
        credibilidade_fonte=pontos.credibilidade_fonte,
        analise_ia=analise_ia,
        pontos=pontos,
    )



# ---------------------------------------------------------------------------
# Funções internas de cálculo
# ---------------------------------------------------------------------------

def _avaliar_fonte(dominio: str, pontos: _PontosDetalhe) -> tuple[int, int]:
    """
    Avalia a credibilidade do domínio e retorna (score, percentual_credibilidade).

    Verifica se o domínio termina com algum sufixo de alta/média confiança
    para capturar subdomínios (ex: portal.anvisa.gov.br → gov.br).
    """
    dominio_lower = dominio.lower()

    # Alta confiança: verifica sufixo e lista exata
    for d in _DOMINIOS_ALTA_CONFIANCA:
        if dominio_lower.endswith(d):
            pontos.positivos.append(
                f"Fonte de alta credibilidade reconhecida: {dominio}"
            )
            return _SCORE_ALTA, 95

    # Média confiança
    for d in _DOMINIOS_MEDIA_CONFIANCA:
        if dominio_lower.endswith(d):
            pontos.positivos.append(f"Fonte conhecida: {dominio}")
            return _SCORE_MEDIA, 65

    # Baixa confiança
    pontos.atencao.append(
        f"Domínio '{dominio}' não reconhecido como fonte verificada."
    )
    pontos.inconsistencias.append(
        "Verifique a reputação da fonte antes de compartilhar."
    )
    return _SCORE_BAIXA, 30


def _calcular_pontos_evidencia(nivel_evidencia: int, pontos: _PontosDetalhe) -> int:
    """
    Converte o nível de evidência (0-100) da IA em pontos (0-20).

    Args:
        nivel_evidencia: Score de evidência retornado pela IA.
        pontos: Estrutura de pontos para adicionar justificativas.

    Returns:
        Pontos de evidência (0-20).
    """
    pts = round(nivel_evidencia * 0.20)

    if nivel_evidencia >= 70:
        pontos.positivos.append("IA identificou bom nível de embasamento no conteúdo.")
    elif nivel_evidencia >= 40:
        pontos.atencao.append("Nível de evidências moderado detectado pela análise.")
    else:
        pontos.atencao.append("Pouco embasamento ou ausência de dados verificáveis.")
        pontos.inconsistencias.append(
            "Afirmações sem suporte evidente identificado pela IA."
        )

    return pts


def _calcular_pontos_sensacionalismo(
    nivel_sensacionalismo: int, pontos: _PontosDetalhe
) -> int:
    """
    Converte o nível de sensacionalismo (0-100) em pontos (0-10).

    Quanto MENOS sensacionalista, mais pontos são atribuídos.

    Args:
        nivel_sensacionalismo: Score de sensacionalismo da IA (0=neutro, 100=sensacionalista).
        pontos: Estrutura de pontos para adicionar justificativas.

    Returns:
        Pontos (0-10): baixo sensacionalismo = mais pontos.
    """
    pts = round((100 - nivel_sensacionalismo) * 0.10)

    if nivel_sensacionalismo <= 30:
        pontos.positivos.append("Linguagem objetiva e sem sensacionalismo detectado.")
    elif nivel_sensacionalismo <= 60:
        pontos.atencao.append("Traços moderados de linguagem sensacionalista.")
    else:
        pontos.atencao.append("Alto grau de sensacionalismo detectado no conteúdo.")
        pontos.inconsistencias.append(
            "Linguagem altamente sensacionalista pode indicar apelo emocional "
            "em detrimento de informação verificável."
        )

    return pts


def _somar_score(pontos: _PontosDetalhe) -> int:
    """
    Soma todos os componentes de pontuação e limita entre 0 e 100.

    Args:
        pontos: Estrutura com todos os scores parciais.

    Returns:
        Score final inteiro entre 0 e 100.
    """
    total = (
        pontos.score_fonte
        + pontos.score_autor
        + pontos.score_data
        + pontos.score_referencias
        + pontos.score_evidencias
        + pontos.score_sensacionalismo
    )

    return max(0, min(100, total))


def _montar_resposta(
    score: int,
    tipo: str,
    titulo: str | None,
    resumo: str,
    dominio: str,
    credibilidade_fonte: int,
    analise_ia: AIAnalysis,
    pontos: _PontosDetalhe,
) -> AnalysisResponse:
    """
    Monta o objeto AnalysisResponse final com todos os campos.

    Args:
        score: Score calculado (0-100).
        tipo: 'url' ou 'image'.
        titulo: Título extraído (pode ser None).
        resumo: Resumo gerado pela IA.
        dominio: Domínio da fonte.
        credibilidade_fonte: Percentual de credibilidade da fonte.
        analise_ia: Análise semântica da IA.
        pontos: Detalhes de pontuação para justificativas.

    Returns:
        AnalysisResponse completo.
    """
    # Normaliza indicadores de referências para o response
    if pontos.score_referencias == 15:
        referencias_score = 100
    elif pontos.score_referencias == 5:
        referencias_score = 50
    else:
        referencias_score = 0

    return AnalysisResponse(
        score=score,
        classificacao=classificar_score(score),
        tipo=tipo,
        titulo=titulo,
        resumo=resumo,
        fonte=FonteInfo(nome=dominio, credibilidade=credibilidade_fonte),
        indicadores=Indicadores(
            evidencias=analise_ia.evidencia,
            referencias=referencias_score,
            sensacionalismo=analise_ia.sensacionalismo,
        ),
        pontos_positivos=pontos.positivos or ["Nenhum ponto positivo identificado."],
        pontos_atencao=pontos.atencao or ["Nenhum ponto de atenção identificado."],
        possiveis_inconsistencias=(
            pontos.inconsistencias or ["Nenhuma inconsistência identificada."]
        ),
    )
