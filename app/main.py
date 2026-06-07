"""
Ponto de entrada da aplicação FakeCheck AI.

Configura o FastAPI com CORS, logging, rotas e documentação automática.
Todas as configurações sensíveis são carregadas via variáveis de ambiente.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import HealthResponse
from app.routes.analysis import router as analysis_router

# Carrega variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instância do FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FakeCheck AI",
    description=(
        "API para análise de confiabilidade de URLs e imagens. "
        "Retorna um score objetivo calculado por regras de backend, "
        "com suporte de IA para interpretação semântica do conteúdo."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — permite requisições de qualquer origem em desenvolvimento
# Em produção, restrinja para os domínios da sua aplicação frontend
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
app.include_router(analysis_router)


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["Saúde"],
    summary="Health Check",
    description="Verifica se a API está online. Útil para monitoramento e deploy.",
)
async def health_check() -> HealthResponse:
    """Endpoint de saúde para monitoramento da API."""
    return HealthResponse(status="online")


# ---------------------------------------------------------------------------
# Startup log
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    model = os.getenv("OPENROUTER_MODEL", "não configurado")
    env = os.getenv("APP_ENV", "development")
    logger.info("FakeCheck AI iniciado — ambiente: %s | modelo IA: %s", env, model)
