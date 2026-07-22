from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status

from app import __version__
from app.config import Settings
from app.demo_guard import HardRateLimitError
from app.models import HealthResponse, MetaResponse, QARequest, QAResponse
from app.service import QAService


def create_app(settings: Settings | None = None, *, mount_ui: bool = False) -> FastAPI:
    resolved = settings or Settings.from_env()
    qa_service = QAService(resolved)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.qa_service = qa_service
        yield

    application = FastAPI(
        title="史鉴 RAG API",
        description="面向历史学习的可溯源混合检索问答 API",
        version=__version__,
        lifespan=lifespan,
    )

    def service(request: Request) -> QAService:
        return request.app.state.qa_service

    def client_identifier(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", maxsplit=1)[0].strip()
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    @application.get(
        "/healthz",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Database is unavailable"}},
        tags=["system"],
    )
    def health(request: Request, response: Response) -> HealthResponse:
        result = service(request).health()
        if result.status == "unhealthy":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return result

    @application.get(
        "/readyz",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Database or index unavailable"}},
        tags=["system"],
    )
    def readiness(request: Request, response: Response) -> HealthResponse:
        qa = service(request)
        result = qa.health()
        if not qa.ready():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return result

    @application.get("/api/v1/meta", response_model=MetaResponse, tags=["system"])
    def metadata(request: Request) -> MetaResponse:
        return service(request).meta()

    @application.post("/api/v1/qa", response_model=QAResponse, tags=["qa"])
    def qa(payload: QARequest, request: Request) -> QAResponse:
        try:
            return service(request).answer(payload, client_identifier(request))
        except HardRateLimitError as exc:
            raise HTTPException(
                status_code=429,
                detail="request_rate_limit",
                headers={"Retry-After": str(exc.retry_after)},
            ) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    if mount_ui:
        import gradio as gr

        from ui.gradio_app import build_demo

        css_path = resolved.root_dir / "style.css"
        application = gr.mount_gradio_app(
            application,
            build_demo(service=qa_service),
            path="/",
            theme=gr.themes.Soft(),
            css=css_path.read_text(encoding="utf-8") if css_path.is_file() else None,
        )
    return application


app = create_app(mount_ui=True)
