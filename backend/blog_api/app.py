from fastapi import FastAPI

from blog_core.app_factory import create_base_app


def create_app() -> FastAPI:
    return create_base_app("blog-api")


app = create_app()
