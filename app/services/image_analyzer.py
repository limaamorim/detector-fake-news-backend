"""
Service responsável por extrair texto de imagens via OCR.

Utiliza EasyOCR com suporte a português e inglês.
O reader é instanciado uma única vez no módulo para evitar recarregamento
do modelo a cada requisição (operação custosa em memória e tempo).

Suporta formatos: jpg, jpeg, png, webp.
"""

import io
import logging
import re
from functools import lru_cache

import easyocr
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Formatos aceitos para upload de imagem
FORMATOS_ACEITOS = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
EXTENSOES_ACEITAS = {".jpg", ".jpeg", ".png", ".webp"}

# Confiança mínima do OCR para considerar um bloco de texto válido
_CONFIANCA_MINIMA = 0.2


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
    return easyocr.Reader(["pt"], gpu=False)


def extrair_texto_imagem(dados_imagem: bytes) -> str:
    """Extrai todo o texto presente em uma imagem usando OCR.

    Adiciona normalizações pós-OCR para reduzir erros comuns (principalmente
    acentos e trocas típicas entre caracteres parecidos).
    """
    try:
        imagem = _abrir_imagem(dados_imagem)
        array_imagem = np.array(imagem)
    except Exception as e:
        raise ValueError(f"Imagem inválida ou corrompida: {str(e)}")

    reader = _get_reader()

    logger.info("Executando OCR na imagem...")
    resultados = reader.readtext(array_imagem)
    del array_imagem

    blocos: list[str] = [
        texto.strip()
        for (_bbox, texto, confianca) in resultados
        if confianca >= _CONFIANCA_MINIMA and texto.strip()
    ]

    texto_final = " ".join(blocos)
    texto_final = _normalizar_texto_ocr(texto_final)

    logger.info("OCR concluído: %d blocos extraídos.", len(blocos))
    import gc
    gc.collect()
    return texto_final


def _normalizar_texto_ocr(texto: str) -> str:
    """Normalizações determinísticas para acentos e erros comuns de OCR."""
    if not texto:
        return ""

    t = texto

    # Normaliza espaços
    t = " ".join(t.split())

    # Correções pontuais (casos frequentes em PT-BR)
    # Mantemos poucas regras para não distorcer texto legítimo.
    correcao = {
        "ÁCUA": "ÁGUA",
        "ÁCUA ": "ÁGUA ",
        "ACUA": "ÁGUA",
        "DOEIIÇAS": "DOENÇAS",
        "DOENIIÇAS": "DOENÇAS",
        "DOENÇAS": "DOENÇAS",
        "DOE NÇAS": "DOENÇAS",
        "DOENÇAS.": "DOENÇAS.",
    }

    for k, v in correcao.items():
        t = t.replace(k, v)

    # Heurística para pequenas duplicações e ruído
    # Ex.: "DOOENÇAS" -> "DOENÇAS" (não remove letras muito agressivamente)
    t = re.sub(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ])\1{1,}", r"\1", t)

    return t



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
    """Abre e normaliza a imagem para melhorar a leitura do OCR."""
    imagem = Image.open(io.BytesIO(dados))

# Reduz imagens muito grandes para economizar memória
    MAX_SIZE = (1200, 1200)
    imagem.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

    # Normaliza modo
    if imagem.mode in ("RGBA", "P", "LA"):
        imagem = imagem.convert("RGB")

    # Grayscale
    imagem = imagem.convert("L")

    # Aumenta contraste automaticamente (reduz problemas por iluminação)
    try:
        from PIL import ImageOps

        imagem = ImageOps.autocontrast(imagem)
    except Exception:
        pass

    # Binarização (limiar adaptado simples via Otsu se disponível)
    try:
        # Evita adicionar dependência forte; se não funcionar, cai no fallback.
        import numpy as _np

        arr = _np.array(imagem)
        # Otsu simples
        hist, bin_edges = _np.histogram(arr.flatten(), bins=256, range=(0, 255))
        total = arr.size
        sum_total = _np.dot(_np.arange(256), hist)
        sum_b, w_b, w_f = 0.0, 0.0, 0.0
        max_var, threshold = -1.0, 140
        for t in range(256):
            w_b += hist[t]
            if w_b == 0:
                continue
            w_f = total - w_b
            if w_f == 0:
                break
            sum_b += t * hist[t]
            m_b = sum_b / w_b
            m_f = (sum_total - sum_b) / w_f
            var_between = w_b * w_f * (m_b - m_f) ** 2
            if var_between > max_var:
                max_var = var_between
                threshold = t

        imagem = imagem.point(lambda x: 0 if x < threshold else 255, "1")
    except Exception:
        # Fallback para threshold fixo (mantém compatibilidade)
        imagem = imagem.point(lambda x: 0 if x < 140 else 255, "1")

    # Volta para RGB para compatibilidade com o EasyOCR
    imagem = imagem.convert("RGB")
    return imagem

