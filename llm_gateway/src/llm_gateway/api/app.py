"""
api/app.py — Fabrique de l'application FastAPI.

create_app(config) compose explicitement toutes les dépendances (connexions
Redis, stores, load balancer) et les attache à app.state.deps. Le reset des
fenêtres RPM est un geste du lifespan de l'API — plus jamais un effet de bord
d'import (cf. docs/arch/llm-module-package-refactor.md §2.3).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_gateway import __version__
from llm_gateway.api.deps import GatewayDeps, build_deps
from llm_gateway.api.metrics import install_collector
from llm_gateway.api.routes import router
from llm_gateway.config import Settings, get_settings
from llm_gateway.telemetry.logger import configure_logging, get_logger

logger = get_logger(__name__)


def _make_lifespan(deps: GatewayDeps):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Reset des fenêtres RPM : une fois, au démarrage de l'API seulement.
        # (Un redémarrage de worker ou un import de module ne touche plus les
        # compteurs en cours — dépassement de quota free-tier évité.)
        try:
            deps.limiter.reset_windows()
            logger.info("Fenêtres RPM remises à zéro au démarrage de l'API.")
        except Exception as e:
            logger.warning(f"Reset RPM au démarrage impossible (non-fatal): {e}")

        # Warm-up de la connexion broker Celery avant la première requête.
        try:
            from llm_gateway.worker.task_worker import celery_app
            conn = celery_app.connection()
            conn.ensure_connection(max_retries=5)
            conn.release()
            logger.info("Celery broker connection warmed up.")
        except Exception as e:
            logger.warning(f"Celery broker warm-up failed (non-fatal): {e}")
        yield

    return lifespan


def create_app(config: Settings | None = None, deps: GatewayDeps | None = None) -> FastAPI:
    """Compose l'application. `deps` permet d'injecter des ports en mémoire (tests, mode embarqué)
    à la place des connexions Redis construites par build_deps()."""
    settings = config or (deps.settings if deps is not None else get_settings())
    configure_logging(settings.telemetry)
    deps = deps if deps is not None else build_deps(settings)
    install_collector(deps)

    app = FastAPI(
        title="llm-gateway",
        description="Gateway asynchrone multi-fournisseur LLM : micro-batching, SWRR, disjoncteur, catégories enfichables.",
        version=__version__,
        lifespan=_make_lifespan(deps),
    )
    app.state.deps = deps

    if settings.api.cors_origins:   # vide = aucun middleware CORS (défaut) ; ["*"] = tout autoriser
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(router)
    return app
