"""
Rotas da API para análise de URLs e imagens.

As rotas são finas (thin controllers): apenas recebem a requisição,
delegam para os services correspondentes e retornam a resposta.
Nenhuma lógica de negócio deve residir aqui.
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.schemas import AnalysisResponse, URLAnalysisRequest
from app.services.ai_service import analisar_texto_com_ia
from app.services.image_analyzer import extrair_texto_imagem, validar_imagem
from app.services.scoring_service import calcular_score_imagem, calcular_score_url
from app.services.url_extractor import extrair_conteudo_url
from app.utils.helpers import sanitizar_texto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["Análise"])

# Limite de tamanho para imagens enviadas (10MB)
_TAMANHO_MAXIMO_IMAGEM = 10 * 1024 * 1024


@router.post(
    "/url",
    response_model=AnalysisResponse,
    summary="Analisar URL",
    description=(
        "Recebe uma URL, extrai o conteúdo da página e retorna um score de "
        "confiabilidade calculado por regras objetivas do backend."
    ),
)
async def analisar_url(request: URLAnalysisRequest) -> AnalysisResponse:
    """
    Endpoint para análise de URLs de notícias, artigos e páginas web.

    Fluxo:
    1. Valida URL (feito pelo schema Pydantic).
    2. Extrai conteúdo via Trafilatura ou BeautifulSoup.
    3. Verifica quantidade mínima de texto.
    4. Analisa semanticamente via IA (sinais auxiliares).
    5. Calcula score via regras do backend.
    6. Retorna análise completa.
    """
    logger.info("Requisição de análise de URL recebida: %s", request.url)

    # --- Extração de conteúdo ---
    try:
        conteudo = extrair_conteudo_url(request.url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Erro inesperado na extração de URL: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível acessar a URL fornecida. Verifique se ela está disponível.",
        )

    # --- Validação de conteúdo mínimo ---
    if conteudo.contagem_palavras < 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Conteúdo insuficiente para análise confiável. "
                f"Encontradas {conteudo.contagem_palavras} palavras (mínimo: 100)."
            ),
        )

    # --- Análise semântica via IA ---
    texto_para_ia = sanitizar_texto(conteudo.texto)
    analise_ia = await analisar_texto_com_ia(texto_para_ia)

    # --- Cálculo do score (regras do backend) ---
    resultado = calcular_score_url(conteudo, analise_ia)

    logger.info(
        "Análise de URL concluída: score=%d, classificação=%s",
        resultado.score,
        resultado.classificacao,
    )

    return resultado


@router.post(
    "/image",
    response_model=AnalysisResponse,
    summary="Analisar Imagem",
    description=(
        "Recebe uma imagem (jpg, jpeg, png, webp), extrai texto via OCR "
        "e retorna um score de confiabilidade."
    ),
)
async def analisar_imagem(
    file: UploadFile = File(..., description="Imagem para análise (jpg, jpeg, png, webp)"),
) -> AnalysisResponse:
    """
    Endpoint para análise de imagens contendo texto ou manchetes.

    Fluxo:
    1. Valida formato do arquivo.
    2. Valida tamanho.
    3. Extrai texto via EasyOCR.
    4. Verifica se algum texto foi encontrado.
    5. Analisa semanticamente via IA.
    6. Calcula score via regras do backend.
    7. Retorna análise completa.
    """
    logger.info("Requisição de análise de imagem recebida: %s", file.filename)

    # --- Validação de formato ---
    try:
        validar_imagem(
            content_type=file.content_type or "",
            filename=file.filename or "",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        )

    # --- Leitura e validação de tamanho ---
    dados_imagem = await file.read()

    if len(dados_imagem) > _TAMANHO_MAXIMO_IMAGEM:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo muito grande. Tamanho máximo: 10MB.",
        )

    if not dados_imagem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo de imagem vazio.",
        )

    # --- OCR ---
    try:
        texto_extraido = extrair_texto_imagem(dados_imagem)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Erro no OCR: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar a imagem. Tente novamente.",
        )

    # --- Validação de texto extraído ---
    if not texto_extraido.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não foi possível identificar texto suficiente na imagem.",
        )

    # --- Análise semântica via IA ---
    texto_para_ia = sanitizar_texto(texto_extraido)
    analise_ia = await analisar_texto_com_ia(texto_para_ia)

    # --- Cálculo do score (regras do backend) ---
    resultado = calcular_score_imagem(analise_ia)

    # Adiciona o texto extraído ao título para contexto
    resultado.titulo = texto_extraido[:200] if texto_extraido else None

    logger.info(
        "Análise de imagem concluída: score=%d, classificação=%s",
        resultado.score,
        resultado.classificacao,
    )

    return resultado
