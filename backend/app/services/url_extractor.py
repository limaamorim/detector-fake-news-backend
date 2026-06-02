"""
Service responsável por extrair conteúdo de URLs.

Estratégia em dois níveis:
1. Trafilatura — extração semântica de alta qualidade para artigos e notícias.
2. BeautifulSoup — fallback manual quando o Trafilatura falha ou retorna pouco conteúdo.

Separa completamente a lógica de extração da lógica de análise.
"""

import logging
import re
from urllib.parse import urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup

from app.models.schemas import ExtractedContent
from app.utils.helpers import extrair_dominio, contar_palavras, detectar_referencias

logger = logging.getLogger(__name__)

# Timeout para requisições HTTP externas
_HTTP_TIMEOUT = 15

# User-Agent genérico para evitar bloqueios simples
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FakeCheckBot/1.0; "
        "+https://fakecheck.ai)"
    )
}


def extrair_conteudo_url(url: str) -> ExtractedContent:
    """
    Extrai título, texto principal, autor, data e domínio de uma URL.

    Tenta primeiro com Trafilatura. Se o resultado for insuficiente,
    usa BeautifulSoup como fallback.

    Args:
        url: URL validada para extração.

    Returns:
        ExtractedContent com os campos disponíveis preenchidos.

    Raises:
        ValueError: Se não for possível obter conteúdo mínimo.
    """
    dominio = extrair_dominio(url)
    logger.info("Iniciando extração de conteúdo: %s", dominio)

    # --- Tentativa 1: Trafilatura ---
    conteudo = _extrair_com_trafilatura(url)

    # --- Fallback: BeautifulSoup ---
    if not conteudo or contar_palavras(conteudo.get("texto", "")) < 50:
        logger.warning("Trafilatura insuficiente, ativando fallback BeautifulSoup.")
        conteudo = _extrair_com_beautifulsoup(url)

    if not conteudo or not conteudo.get("texto"):
        raise ValueError("Não foi possível extrair conteúdo da URL fornecida.")

    texto = conteudo["texto"]
    contagem = contar_palavras(texto)
    tem_referencias = detectar_referencias(texto)

    return ExtractedContent(
        titulo=conteudo.get("titulo"),
        texto=texto,
        autor=conteudo.get("autor"),
        data=conteudo.get("data"),
        dominio=dominio,
        tem_referencias=tem_referencias,
        contagem_palavras=contagem,
    )


# ---------------------------------------------------------------------------
# Extratores internos
# ---------------------------------------------------------------------------

def _extrair_com_trafilatura(url: str) -> dict | None:
    """
    Usa Trafilatura para extrair conteúdo semântico da página.

    Args:
        url: URL da página.

    Returns:
        Dicionário com os campos extraídos ou None em caso de falha.
    """
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return None

        resultado = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            output_format="json",
            with_metadata=True,
        )

        if not resultado:
            return None

        import json
        dados = json.loads(resultado)

        return {
            "titulo": dados.get("title"),
            "texto": dados.get("text", ""),
            "autor": dados.get("author"),
            "data": dados.get("date"),
        }

    except Exception as e:
        logger.warning("Trafilatura falhou: %s", str(e))
        return None


def _extrair_com_beautifulsoup(url: str) -> dict | None:
    """
    Fallback manual com BeautifulSoup para páginas onde o Trafilatura falha.

    Extrai o título da tag <title> e o texto dos parágrafos principais.

    Args:
        url: URL da página.

    Returns:
        Dicionário com título e texto ou None em caso de falha.
    """
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_HTTP_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts, estilos e navegação
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        titulo = soup.title.string.strip() if soup.title else None

        # Coleta parágrafos com conteúdo relevante (> 40 chars)
        paragrafos = [
            p.get_text(separator=" ").strip()
            for p in soup.find_all("p")
            if len(p.get_text()) > 40
        ]
        texto = " ".join(paragrafos)

        # Tenta extrair autor via meta tags comuns
        autor = None
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            if name in ("author", "article:author"):
                autor = meta.get("content")
                break

        return {"titulo": titulo, "texto": texto, "autor": autor, "data": None}

    except Exception as e:
        logger.error("BeautifulSoup fallback falhou: %s", str(e))
        return None
