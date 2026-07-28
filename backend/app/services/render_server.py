"""Playwright HTTP microservice — DOM extraction + PNG rendering.

Two endpoints:
  POST /render        → returns PNG bytes (for Verifier)
  POST /extract-dom   → returns computed DOM tree JSON (for HTML→Penpot converter)
  GET  /health        → liveness check

Run via: uvicorn render_server:app --host 0.0.0.0 --port 4000
"""

import asyncio
import base64
import json
import re
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="Playwright DOM Extraction Service")

_browser = None
_lock = asyncio.Lock()


async def get_browser():
    """Lazy-init shared Playwright Chromium browser."""
    global _browser
    if _browser is not None and _browser.is_connected():
        return _browser
    async with _lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            _browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--font-render-hinting=none",
                ],
            )
    return _browser


class RenderRequest(BaseModel):
    html: str
    width: int = 1080
    height: int = 1080
    format: str = "png"
    wait_until: str = "networkidle"
    wait_for_selector: str | None = None
    wait_for_timeout: int = 3000


class DOMExtractionRequest(BaseModel):
    html: str
    width: int = 1080
    height: int = 1080


@app.get("/health")
async def health():
    return {"status": "ok", "service": "playwright-dom-extraction"}


@app.post("/render")
async def render(req: RenderRequest):
    """Render HTML to PNG and return image bytes."""
    browser = await get_browser()
    page = await browser.new_page(viewport={"width": req.width, "height": req.height})

    try:
        await page.set_content(req.html, wait_until=req.wait_until)

        if req.wait_for_selector:
            try:
                await page.wait_for_selector(req.wait_for_selector, timeout=req.wait_for_timeout)
            except Exception:
                pass

        png_bytes = await page.screenshot(
            type="png",
            clip={"x": 0, "y": 0, "width": req.width, "height": req.height},
            full_page=False,
        )
        return Response(content=png_bytes, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await page.close()


@app.post("/extract-dom")
async def extract_dom(req: DOMExtractionRequest):
    """Render HTML and extract the computed DOM tree with CSS properties."""
    browser = await get_browser()
    page = await browser.new_page(viewport={"width": req.width, "height": req.height})

    try:
        await page.set_content(req.html, wait_until="networkidle")

        # JavaScript that walks the DOM and extracts computed styles + bounding boxes
        dom_tree = await page.evaluate("""(width, height) => {
            function extractNode(el, parentX, parentY) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const tag = el.tagName ? el.tagName.toLowerCase() : 'text';

                // Skip elements with no size (collapsed, hidden, etc.)
                if (rect.width === 0 && rect.height === 0 && tag !== 'text') return null;
                if (style.display === 'none' || style.visibility === 'hidden') return null;

                const node = {
                    tag: tag,
                    id: el.id || '',
                    classList: Array.from(el.classList || []),
                    text: el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
                          ? el.childNodes[0].textContent.trim()
                          : '',
                    x: rect.left,
                    y: rect.top,
                    width: rect.width,
                    height: rect.height,
                    backgroundColor: style.backgroundColor,
                    color: style.color,
                    fontFamily: style.fontFamily,
                    fontSize: parseFloat(style.fontSize) || 16,
                    fontWeight: style.fontWeight,
                    lineHeight: style.lineHeight,
                    letterSpacing: style.letterSpacing,
                    textAlign: style.textAlign,
                    borderRadius: style.borderRadius,
                    opacity: parseFloat(style.opacity) || 1,
                    overflow: style.overflow,
                    children: [],
                    svgContent: null,
                };

                // For .math or .diagram elements, extract SVG if rendered
                if (el.classList && (el.classList.contains('math') || el.classList.contains('diagram'))) {
                    const svg = el.querySelector('svg');
                    if (svg) {
                        node.svgContent = svg.outerHTML;
                    }
                }

                // Recursively process children (elements only, skip text nodes)
                for (const child of el.children) {
                    const childNode = extractNode(child, rect.left, rect.top);
                    if (childNode) node.children.push(childNode);
                }

                return node;
            }

            const body = document.body;
            return { dom: extractNode(body) };
        }""", req.width, req.height)

        return dom_tree

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await page.close()
