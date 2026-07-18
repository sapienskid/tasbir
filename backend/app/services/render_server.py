"""Playwright render microservice — converts HTML to PNG.

This runs inside the Playwright Docker container (mcr.microsoft.com/playwright/python).
Receives HTML over HTTP, renders it in headless Chromium, returns PNG bytes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel


class RenderRequest(BaseModel):
    html: str
    width: int = 1080
    height: int = 1080
    format: str = "png"


_browser = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    from playwright.async_api import async_playwright

    p = await async_playwright().start()
    global _browser
    _browser = await p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    yield
    await _browser.close()
    await p.stop()


app = FastAPI(title="Tasbir Renderer", version="0.1.0", lifespan=lifespan)


@app.post("/render")
async def render(req: RenderRequest):
    if _browser is None:
        raise HTTPException(status_code=503, detail="Browser not ready")

    page = await _browser.new_page(
        viewport={"width": req.width, "height": req.height},
        device_scale_factor=2,
    )
    try:
        await page.set_content(req.html, wait_until="networkidle")
        await page.wait_for_timeout(500)
        buf = await page.screenshot(full_page=False, type=req.format)
        return Response(content=buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await page.close()


@app.get("/health")
async def health():
    return {"status": "ok", "browser": _browser is not None}
