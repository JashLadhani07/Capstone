from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[2]

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"active_page": "overview"}
    )


@router.get("/analysis")
async def analysis_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/analysis.html",
        context={"active_page": "analysis"}
    )


@router.get("/signals")
async def signals_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/signals.html",
        context={"active_page": "signals"}
    )


@router.get("/signals/{signal_id}")
async def signal_detail_page(request: Request, signal_id: str):
    return templates.TemplateResponse(
        request=request,
        name="pages/signal_detail.html",
        context={
            "active_page": "signals",
            "signal_id": signal_id
        }
    )


@router.get("/trials")
async def trials_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/trials.html",
        context={"active_page": "trials"}
    )


@router.get("/agents")
async def agents_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/agents.html",
        context={"active_page": "agents"}
    )


@router.get("/history")
async def history_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/history.html",
        context={"active_page": "history"}
    )


@router.get("/reviews")
async def reviews_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/reviews.html",
        context={"active_page": "reviews"}
    )


@router.get("/assistant")
async def assistant_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/assistant.html",
        context={"active_page": "assistant"}
    )