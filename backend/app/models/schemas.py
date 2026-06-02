"""
Schemas Pydantic para validação de entrada e saída da API.

Centraliza todos os contratos de dados do sistema em um único lugar,
garantindo tipagem forte e validação automática pelo FastAPI.
"""

from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class URLAnalysisRequest(BaseModel):
    """Payload para análise de URL."""

    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL deve começar com http:// ou https://")
        return v


# ---------------------------------------------------------------------------
# Submodels de resposta
# ---------------------------------------------------------------------------

class FonteInfo(BaseModel):
    """Informações sobre a fonte/domínio analisado."""

    nome: str
    credibilidade: int  # 0-100


class Indicadores(BaseModel):
    """Métricas extraídas pela IA e pelo scoring service."""

    evidencias: int       # 0-100
    referencias: int      # 0-100
    sensacionalismo: int  # 0-100


# ---------------------------------------------------------------------------
# Response principal
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    """Resposta padrão para análises de URL e imagem."""

    score: int
    classificacao: str
    tipo: str  # "url" | "image"
    titulo: Optional[str] = None
    resumo: str
    fonte: Optional[FonteInfo] = None
    indicadores: Indicadores
    pontos_positivos: list[str]
    pontos_atencao: list[str]
    possiveis_inconsistencias: list[str]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Resposta do endpoint de saúde."""

    status: str


# ---------------------------------------------------------------------------
# Estrutura interna usada entre services (não exposta na API)
# ---------------------------------------------------------------------------

class ExtractedContent(BaseModel):
    """Conteúdo extraído de uma URL antes da análise."""

    titulo: Optional[str] = None
    texto: str
    autor: Optional[str] = None
    data: Optional[str] = None
    dominio: str
    tem_referencias: bool = False
    contagem_palavras: int = 0


class AIAnalysis(BaseModel):
    """Resultado retornado pela IA após análise do texto."""

    sensacionalismo: int   # 0-100 (quanto mais alto, mais sensacionalista)
    evidencia: int         # 0-100 (quanto mais alto, mais evidências)
    resumo: str
    afirmacoes: list[str]
