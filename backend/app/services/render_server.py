"""Playwright render microservice — converts HTML to PNG.

This runs inside the Playwright Docker container (mcr.microsoft.com/playwright/python).
Receives HTML over HTTP, renders it in headless Chromium, returns PNG bytes.

All wait parameters are forwarded from the caller so Tailwind CDN, Google Fonts,
and any JS-driven rendering (Mermaid, KaTeX) complete before the screenshot.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel


class RenderRequest(BaseModel):
    html: str
    width: int = 1080
    height: int = 1080
    format: str = "png"
    # Wait strategy — forwarded from the backend renderer client.
    # "networkidle" ensures Tailwind CDN + Google Fonts have loaded.
    wait_until: str = "networkidle"
    # Optional CSS selector to wait for before screenshotting (e.g. Mermaid sentinel).
    wait_for_selector: Optional[str] = None
    # Extra milliseconds to wait after content is ready (gives Tailwind time to paint).
    wait_for_timeout: int = 2000


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


app = FastAPI(title="Tasbir Renderer", version="0.2.0", lifespan=lifespan)


@app.post("/render")
async def render(req: RenderRequest):
    if _browser is None:
        raise HTTPException(status_code=503, detail="Browser not ready")

    page = await _browser.new_page(
        viewport={"width": req.width, "height": req.height},
        device_scale_factor=2,
    )
    try:
        # wait_until controls when set_content resolves — "networkidle" waits for
        # Tailwind CDN + Google Fonts HTTP requests to complete.
        await page.set_content(req.html, wait_until=req.wait_until)

        # Wait for a JS-sentinel selector if requested (e.g. Mermaid diagrams).
        if req.wait_for_selector:
            try:
                await page.wait_for_selector(req.wait_for_selector, timeout=5000)
            except Exception:
                pass  # selector timeout is non-fatal — screenshot anyway

        # Additional settle time so Tailwind utility classes paint to screen.
        # Default 2 s; callers can override via wait_for_timeout.
        await page.wait_for_timeout(req.wait_for_timeout)

        buf = await page.screenshot(full_page=False, type=req.format)
        return Response(content=buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await page.close()


@app.get("/health")
async def health():
    return {"status": "ok", "browser": _browser is not None}
