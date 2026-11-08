from fastapi import FastAPI


def create_base_app(title: str, *, openapi_url: str | None = None) -> FastAPI:
    """Return a FastAPI app with the shared secure defaults.

    The interactive documentation routes stay off. An app that publishes an
    OpenAPI document passes its own `openapi_url`. The only route is
    `GET /healthz`, which returns no data and needs no authentication.
    """
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=openapi_url)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
