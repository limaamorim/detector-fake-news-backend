"""
Funções utilitárias reutilizáveis por todos os services.

Mantém lógicas simples e independentes de negócio fora dos services
para evitar duplicação e facilitar testes unitários.
"""

import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def extrair_dominio(url: str) -> str:
    """
    Extrai o domínio limpo de uma URL.

    Exemplos:
        https://www.g1.globo.com/noticia -> g1.globo.com
        https://gov.br/saude -> gov.br

    Args:
        url: URL completa.

    Returns:
        String do domínio sem 'www.'.
    """
    try:
        parsed = urlparse(url)
        dominio = parsed.netloc.lower()
        return dominio.removeprefix("www.")
    except Exception:
        return ""


def contar_palavras(texto: str) -> int:
    """
    Conta o número de palavras em um texto.

    Args:
        texto: Texto de entrada.

    Returns:
        Número inteiro de palavras.
    """
    if not texto:
        return 0
    return len(texto.split())


def detectar_referencias(texto: str) -> bool:
    """
    Verifica se o texto contém padrões de referências externas.

    Considera como referência: menções a estudos, pesquisas, fontes,
    URLs explícitas e termos indicativos de embasamento.

    Args:
        texto: Texto extraído do conteúdo.

    Returns:
        True se referências forem detectadas.
    """
    padroes = [
        r"https?://",
        r"segundo\s+\w+",
        r"de acordo com",
        r"pesquisa\s+(da|do|de)",
        r"estudo\s+(da|do|de|publicado)",
        r"fonte[:\s]",
        r"\[\d+\]",          # citações numéricas [1], [2]
        r"et al\.",
        r"doi\.org",
    ]
    texto_lower = texto.lower()
    return any(re.search(p, texto_lower) for p in padroes)


def sanitizar_texto(texto: str, max_chars: int = 4000) -> str:
    """
    Limpa e trunca o texto antes de enviar para a IA.

    Remove espaços excessivos e garante que o texto não exceda
    o limite de tokens do modelo.

    Args:
        texto: Texto bruto.
        max_chars: Limite máximo de caracteres.

    Returns:
        Texto sanitizado e truncado.
    """
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:max_chars]


def classificar_score(score: int) -> str:
    """
    Retorna a classificação textual com base no score numérico.

    Args:
        score: Valor de 0 a 100.

    Returns:
        String com o rótulo da classificação.
    """
    if score >= 80:
        return "Alta Confiabilidade"
    elif score >= 60:
        return "Confiabilidade Moderada"
    elif score >= 40:
        return "Conteúdo Duvidoso"
    else:
        return "Possível Desinformação"
