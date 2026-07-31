"""HTML page routes (Jinja2)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.providers.registry import get_registry
from app.services import novel_service

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    novels = novel_service.list_novels(db)
    return templates.TemplateResponse(
        request, "index.html", {"novels": novels}
    )


@router.get("/create", response_class=HTMLResponse)
def create_form(request: Request):
    providers = get_registry().list_providers()
    return templates.TemplateResponse(
        request, "create.html", {"providers": providers}
    )


@router.get("/novels/{novel_id}", response_class=HTMLResponse)
def novel_page(novel_id: int, request: Request, db: Session = Depends(get_db)):
    novel = novel_service.get_novel(db, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    providers = get_registry().list_providers()
    return templates.TemplateResponse(
        request, "novel.html", {"novel": novel, "providers": providers}
    )
