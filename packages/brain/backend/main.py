import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.routers.websocket import router as ws_router
from backend.routers.chat import router as chat_router
from backend.routers.tts import router as tts_router
from backend.routers.stt import router as stt_router
from backend.routers.gaps import router as gaps_router
from backend.routers.desktop import router as desktop_router
from backend.routers.pages import router as pages_router
from backend.routers.index import router as index_router
from backend.routers.runtime import router as runtime_router
from backend.routers.web_proxy import router as web_proxy_router
from backend.routers.reflect import router as reflect_router
from backend.routers.fleet import router as fleet_router
from backend.routers.analyze import router as analyze_router
from backend.routers.channels import router as channels_router
from backend.routers.presence import router as presence_router
from backend.routers.agents import router as agents_router
from backend.routers.pocket import router as pocket_router
from backend.routers.pocket_extended import router as pocket_ext_router
from backend.routers.ios_bridge import router as ios_bridge_router
from backend.routers.identity import router as identity_router
from backend.routers.emergency import router as emergency_router
from backend.routers.host_metrics import router as host_metrics_router
from backend.routers.hud import router as hud_router
from backend.routers.llm_models import router as llm_models_router
from backend.routers.perception import router as perception_router
from backend.routers.kiosk import router as kiosk_router, mount_kiosk_static
from backend.routers.windows import router as windows_router
from backend.routers.evolve import router as evolve_router
from backend.routers.scout import router as scout_router
from backend.routers.lab import router as lab_router

# Registra strumenti
import backend.core.tools  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("JANIS")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
MONOREPO_ROOT = Path(__file__).resolve().parents[3]
CLIENT_WEB_DIR = MONOREPO_ROOT / "packages" / "client-web"
CLIENT_STATIC = CLIENT_WEB_DIR / "static"

app = FastAPI(
    title="JANIS",
    description="Just Another Neuralgic Improving Server",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(chat_router)
app.include_router(tts_router)
app.include_router(stt_router)
app.include_router(gaps_router)
app.include_router(desktop_router)
app.include_router(pages_router)
app.include_router(index_router)
app.include_router(runtime_router)
app.include_router(web_proxy_router)
app.include_router(reflect_router)
app.include_router(fleet_router)
app.include_router(analyze_router)
app.include_router(channels_router)
app.include_router(presence_router)
app.include_router(agents_router)
app.include_router(pocket_router)
app.include_router(pocket_ext_router)
app.include_router(ios_bridge_router)
app.include_router(identity_router)
app.include_router(emergency_router)
app.include_router(host_metrics_router)
app.include_router(hud_router)
app.include_router(llm_models_router)
app.include_router(perception_router)
app.include_router(kiosk_router)
app.include_router(windows_router)
app.include_router(evolve_router)
app.include_router(scout_router)
app.include_router(lab_router)
mount_kiosk_static(app)


@app.get("/client")
async def client_page():
    page = CLIENT_WEB_DIR / "ide.html"
    if page.exists():
        return FileResponse(page, headers={"Cache-Control": "no-store, must-revalidate"})
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"error": "client not found"}


@app.get("/brain")
async def brain_page():
    page = FRONTEND_DIR / "brain.html"
    if page.exists():
        return FileResponse(page)
    return {"error": "brain page not found"}


@app.get("/widget")
async def widget_page():
    page = FRONTEND_DIR / "widget.html"
    if page.exists():
        return FileResponse(page)
    return {"error": "widget page not found"}


@app.get("/setup")
async def setup_page():
    page = FRONTEND_DIR / "setup.html"
    if page.exists():
        return FileResponse(page)
    return {"error": "setup page not found"}


@app.get("/")
async def root():
    client = CLIENT_WEB_DIR / "ide.html"
    if client.exists():
        return FileResponse(client, headers={"Cache-Control": "no-store, must-revalidate"})
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"status": "online", "service": "JANIS"}


@app.get("/drafts")
async def avatar_drafts():
    page = FRONTEND_DIR / "drafts.html"
    if page.exists():
        return FileResponse(page)
    return {"error": "drafts page not found"}


# Asset statici frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
if CLIENT_STATIC.exists():
    app.mount("/client-static", StaticFiles(directory=str(CLIENT_STATIC)), name="client-static")


@app.middleware("http")
async def dev_no_cache_static(request, call_next):
    """In dev, evita cache aggressiva su JS/CSS durante lavoro in Cursor."""
    response = await call_next(request)
    path = request.url.path
    if (
        path.startswith("/static/")
        or path.startswith("/client-static/")
        or path.startswith("/kiosk-static/")
    ) and (
        path.endswith(".js") or path.endswith(".css") or path.endswith(".html")
    ):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.on_event("startup")
async def startup():
    if not os.path.isabs(settings.MEMORY_DIR):
        settings.MEMORY_DIR = os.path.join(settings.JANIS_PROJECT_DIR, "data", "memory")
    os.makedirs(settings.MEMORY_DIR, exist_ok=True)
    from backend.core.ollama_service import ensure_ollama_running
    from backend.core.llm_router import get_active_provider
    if not await ensure_ollama_running():
        logger.warning("Ollama offline — la chat non funzionerà finché non è avviato")
    provider = await get_active_provider()
    logger.info("JANIS online — provider: %s, modello: %s", provider.get("active"), settings.OLLAMA_MODEL)
    import asyncio
    from backend.core.ollama_model_router import probe_all_models

    async def _probe_models_bg():
        try:
            result = await probe_all_models(force=True)
            logger.info(
                "Ollama probe: %s modelli OK — fast=%s balanced=%s capable=%s",
                len(result.get("working") or []),
                (result.get("by_tier") or {}).get("fast"),
                (result.get("by_tier") or {}).get("balanced"),
                (result.get("by_tier") or {}).get("capable"),
            )
        except Exception:
            logger.exception("Probe modelli Ollama fallito")

    asyncio.create_task(_probe_models_bg(), name="janis-ollama-probe")
    logger.info("Workspace: %s", settings.JANIS_WORKSPACE)
    from backend.core.evolve_paths import ensure_workspace_dirs
    paths = ensure_workspace_dirs()
    logger.info("Monorepo evolve: %s", paths.get("evolve"))
    logger.info("Web proxy attivo: /api/web/proxy, /api/web/check")
    from backend.core.tech_analysis import seed_baseline_research
    from backend.core.cursor_win_patch import apply_cursor_sdk_patches

    apply_cursor_sdk_patches()
    seeded = seed_baseline_research()
    if seeded:
        logger.info("Roadmap seed: analisi OpenClaw/Odysseus caricata")
    from backend.core.channels.telegram import start_telegram_polling
    from backend.core.scheduler import start_scheduler

    await start_telegram_polling()
    await start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    from backend.core.channels.telegram import stop_telegram_polling
    from backend.core.scheduler import stop_scheduler

    await stop_telegram_polling()
    await stop_scheduler()


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
