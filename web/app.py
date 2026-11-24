from contextlib import asynccontextmanager
import asyncio
import logging
import re
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import init_db, get_engine, prune_old_notifications
from core.state_hub import state_hub
from web.routes import api_router, public_router, proxy_game_asset, close_asset_client

logger = logging.getLogger(__name__)


class SSEAwareGZipMiddleware:
    """Обёртка над GZipMiddleware, отключающая буферизующее сжатие для SSE-потока /live/stream."""

    def __init__(self, app, minimum_size: int = 500):
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and str(scope.get("path", "")).endswith("/live/stream"):
            await self.app(scope, receive, send)
            return
        await self.gzip(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    await init_db(engine)
    try:
        await prune_old_notifications(engine, days=settings.NOTIFICATIONS_RETENTION_DAYS)
    except Exception as pe:
        logger.warning("Could not prune old notifications on boot: %s", pe)

    # Очистка зависших активных пресетов после перезапуска процесса (stale PresetRunState guard)
    try:
        from sqlalchemy import update
        from core.database import get_session
        from core.models import BossPreset
        async with get_session(engine) as session:
            await session.execute(
                update(BossPreset)
                .where(BossPreset.is_running == True)
                .values(is_running=False, last_status="Сброшен при перезапуске")
            )
            await session.commit()
        state_hub.clear_preset_state(1)
    except Exception as se:
        logger.warning("Could not reset stale running boss presets on boot: %s", se)

    from bot.handlers import bot_context
    if bot_context.db_engine is None:
        bot_context.db_engine = engine
    if getattr(bot_context, "state_hub", None) is None:
        bot_context.state_hub = state_hub

    standalone_scheduler = None
    if bot_context.player_api is None and bot_context.boss_worker is None:
        try:
            from core.database import get_session
            from core.models import Account, SessionData
            from core.scheduler import create_scheduler
            from sqlalchemy import select
            from client.auth_provider import AuthProvider
            from client.http_client import GameHttpClient
            from client.api.player import PlayerAPI
            from client.api.boss import BossAPI
            from client.api.prison import PrisonAPI
            from client.api.social import SocialAPI
            from workers.routine_worker import RoutineWorker
            from workers.boss_worker import BossWorker
            from workers.prison_worker import PrisonWorker
            from workers.social_worker import SocialWorker

            has_token = False
            async with get_session(engine) as session:
                stmt = select(Account).order_by(Account.id.asc()).limit(1)
                acc = (await session.execute(stmt)).scalar_one_or_none()
                if not acc:
                    acc = Account(phone="+70000000000", is_active=True)
                    session.add(acc)
                    await session.flush()
                    session.add(SessionData(account_id=acc.id))
                    await session.commit()
                else:
                    s_stmt = select(SessionData).where(SessionData.account_id == acc.id)
                    s_row = (await session.execute(s_stmt)).scalar_one_or_none()
                    has_token = bool(s_row and (s_row.access_token or s_row.refresh_token or s_row.tg_session_string))
                acc_id = acc.id

            auth_provider = AuthProvider(account_id=acc_id, db_engine=engine)
            http_client = GameHttpClient(auth_provider=auth_provider)
            player_api = PlayerAPI(http_client=http_client)
            boss_api = BossAPI(http_client=http_client)
            prison_api = PrisonAPI(http_client=http_client)
            social_api = SocialAPI(http_client=http_client)

            routine_worker = RoutineWorker(
                account_id=acc_id,
                player_api=player_api,
                db_engine=engine,
                social_api=social_api,
            )
            boss_worker = BossWorker(
                account_id=acc_id,
                boss_api=boss_api,
                db_engine=engine,
                prison_api=prison_api,
                player_api=player_api,
                state_hub=state_hub,
            )
            prison_worker = PrisonWorker(
                account_id=acc_id,
                prison_api=prison_api,
                player_api=player_api,
                db_engine=engine,
                state_hub=state_hub,
            )
            social_worker = SocialWorker(account_id=acc_id, social_api=social_api, db_engine=engine)
            routine_worker.prison_worker = prison_worker

            bot_context.player_api = player_api
            bot_context.boss_api = boss_api
            bot_context.prison_api = prison_api
            bot_context.social_api = social_api
            bot_context.routine_worker = routine_worker
            bot_context.boss_worker = boss_worker
            bot_context.prison_worker = prison_worker
            bot_context.social_worker = social_worker

            if bot_context.scheduler is None:
                standalone_scheduler = create_scheduler(
                    routine_worker=routine_worker,
                    boss_worker=boss_worker,
                    prison_worker=prison_worker,
                    social_worker=social_worker,
                )
                bot_context.scheduler = standalone_scheduler
                bot_context.scheduler_controller = getattr(standalone_scheduler, "controller", None)
                standalone_scheduler.start()
                if has_token and bot_context.scheduler_controller is not None:
                    asyncio.create_task(bot_context.scheduler_controller.warmup_all())
        except Exception as e:
            logger.warning("Could not auto-initialize bot_context in web dashboard: %s", e)

    try:
        yield
    finally:
        if standalone_scheduler is not None:
            try:
                standalone_scheduler.shutdown(wait=False)
            except Exception:
                pass
        await close_asset_client()


def create_app() -> FastAPI:
    """Создает и настраивает FastAPI приложение PrisonBot Dashboard."""
    app = FastAPI(
        title="PrisonBot Web Dashboard",
        version="2.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # Prefix rewrite middleware для корректной работы за reverse-proxy с префиксом (например X-Forwarded-Prefix: /prison)
    # Регистрируется ДО GZipMiddleware, чтобы работать с несжатым телом ответа до его сжатия.
    @app.middleware("http")
    async def forwarded_prefix_middleware(request: Request, call_next):
        response = await call_next(request)
        prefix = (request.headers.get("x-forwarded-prefix") or "").strip().rstrip("/")
        if not prefix or not re.fullmatch(r"/[A-Za-z0-9_/-]+", prefix):
            return response

        req_path = request.url.path
        if "/vendor/" in req_path or req_path.startswith("/static/assets/"):
            return response

        ctype = (response.headers.get("content-type") or "").lower()
        if ctype.startswith("text/event-stream") or req_path.endswith("/live/stream"):
            return response
        is_rewritable = (
            ctype.startswith("text/html")
            or ctype.startswith("application/json")
            or "javascript" in ctype
        )
        if not is_rewritable or response.status_code == 304:
            return response

        body_chunks = []
        async for chunk in response.body_iterator:
            body_chunks.append(chunk)
        raw_body = b"".join(body_chunks)

        if not raw_body:
            from starlette.responses import Response
            hdrs = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            return Response(content=raw_body, status_code=response.status_code, headers=hdrs, media_type=response.media_type)

        text = raw_body.decode("utf-8", errors="ignore")
        for quote in ('"', "'", "`"):
            text = text.replace(f"{quote}/api/v1", f"{quote}{prefix}/api/v1")
            text = text.replace(f"{quote}/static/", f"{quote}{prefix}/static/")
            text = text.replace(f'{quote}/static{quote}', f'{quote}{prefix}/static{quote}')

        encoded = text.encode("utf-8")
        from starlette.responses import Response
        hdrs = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(content=encoded, status_code=response.status_code, headers=hdrs, media_type=response.media_type)

    # Cache-Control headers: public for /static/assets/*, no-cache for HTML/JS/CSS
    @app.middleware("http")
    async def add_cache_control_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/assets/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path == "/" or path.endswith((".html", ".js", ".css")) or (path.startswith("/static/") and not path.startswith("/static/assets/")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip compression (70-85% reduction for JSON/JS/CSS), но пропускает SSE /live/stream без буферизации
    app.add_middleware(SSEAwareGZipMiddleware, minimum_size=500)

    # REST API
    app.include_router(public_router)
    app.include_router(api_router)

    # Direct fallback for /assets/... requests from browser
    @app.get("/assets/{rest_path:path}")
    async def root_assets_proxy(rest_path: str):
        return await proxy_game_asset(path=f"assets/{rest_path}")

    # Static files directory
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    # Dynamic index.html route with auto-versioning (?v=<mtime>)
    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return HTMLResponse("Not found", status_code=404)
        content = index_file.read_text(encoding="utf-8")
        styles_file = static_dir / "styles.css"
        app_file = static_dir / "app.js"
        mtimes = [index_file.stat().st_mtime]
        if styles_file.exists():
            mtimes.append(styles_file.stat().st_mtime)
        if app_file.exists():
            mtimes.append(app_file.stat().st_mtime)
        v_tag = str(int(max(mtimes)))

        content = re.sub(r'styles\.css(?:\?v=[^"\'\s>]+)?', f'styles.css?v={v_tag}', content)
        content = re.sub(r'app\.js(?:\?v=[^"\'\s>]+)?', f'app.js?v={v_tag}', content)
        return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, must-revalidate"})

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static_assets")
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static_root")

    return app


app = create_app()
