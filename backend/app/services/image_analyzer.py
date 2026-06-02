"""
Service responsável por extrair texto de imagens via OCR.

Utiliza EasyOCR com suporte a português e inglês.
O reader é instanciado uma única vez no módulo para evitar recarregamento
do modelo a cada requisição (operação custosa em memória e tempo).

Suporta formatos: jpg, jpeg, png, webp.
"""

import io
import logging
from functools import lru_cache
from typing import Optional

import easyocr
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Formatos aceitos para upload de imagem
FORMATOS_ACEITOS = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
EXTENSOES_ACEITAS = {".jpg", ".jpeg", ".png", ".webp"}

# Confiança mínima do OCR para considerar um bloco de texto válido
_CONFIANCA_MINIMA = 0.3


@lru_cache(maxsize=1)
def _get_reader() -> easyocr.Reader:
    """
    Instancia e cacheia o reader do EasyOCR.

    O carregamento do modelo é pesado (~1-2s na primeira chamada),
    por isso é feito apenas uma vez via lru_cache.

    Returns:
        Instância configurada do EasyOCR Reader.
    """
    logger.info("Carregando modelo EasyOCR (pt + en)...")
    return easyocr.Reader(["pt", "en"], gpu=False)


def extrair_texto_imagem(dados_imagem: bytes) -> str:
    """
    Extrai todo o texto presente em uma imagem usando OCR.

    Aplica filtro de confiança para descartar leituras com baixa
    certeza e retorna o texto concatenado por linhas.

    Args:
        dados_imagem: Conteúdo binário da imagem.

    Returns:
        Texto extraído como string única. Retorna string vazia se
        nenhum texto for identificado com confiança suficiente.

    Raises:
        ValueError: Se o formato da imagem for inválido ou corrompido.
    """
    try:
        imagem = _abrir_imagem(dados_imagem)
        array_imagem = np.array(imagem)
    except Exception as e:
        raise ValueError(f"Imagem inválida ou corrompida: {str(e)}")

    reader = _get_reader()

    logger.info("Executando OCR na imagem...")
    resultados = reader.readtext(array_imagem)

    # Filtra por confiança mínima e extrai apenas o texto
    blocos = [
        texto.strip()
        for (_bbox, texto, confianca) in resultados
        if confianca >= _CONFIANCA_MINIMA and texto.strip()
    ]

    texto_final = " ".join(blocos)
    logger.info("OCR concluído: %d blocos extraídos.", len(blocos))

    return texto_final


def validar_imagem(content_type: str, filename: str) -> None:
    """
    Valida se o arquivo enviado é uma imagem aceita pelo sistema.

    Args:
        content_type: MIME type do arquivo (ex: 'image/jpeg').
        filename: Nome original do arquivo.

    Raises:
        ValueError: Se o formato não for suportado.
    """
    import os
    extensao = os.path.splitext(filename)[1].lower()

    if content_type not in FORMATOS_ACEITOS and extensao not in EXTENSOES_ACEITAS:
        raise ValueError(
            f"Formato não suportado: '{extensao}'. "
            f"Use: {', '.join(EXTENSOES_ACEITAS)}"
        )


def _abrir_imagem(dados: bytes) -> Image.Image:
    """
    Abre a imagem a partir de bytes e normaliza para RGB.

    Converte imagens RGBA ou com paleta (modo P) para RGB,
    pois o EasyOCR espera imagens no formato padrão.

    Args:
        dados: Bytes da imagem.

    Returns:
        Objeto PIL.Image em modo RGB.
    """
    imagem = Image.open(io.BytesIO(dados))

    if imagem.mode in ("RGBA", "P", "LA"):
        imagem = imagem.convert("RGB")

    return imagem
