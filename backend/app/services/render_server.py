"""Playwright HTTP microservice — DOM extraction + PNG rendering.

Two endpoints:
  POST /render        → returns PNG bytes (for Verifier)
  POST /extract-dom   → returns computed DOM tree JSON
  GET  /health        → liveness check

Run via: uvicorn render_server:app --host 0.0.0.0 --port 4000
"""

import asyncio
import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="Playwright DOM Extraction Service")

_browser = None
_lock = asyncio.Lock()

# Shared-secret auth between the worker and this service. When set, /render
# and /extract-dom require the X-Render-Key header. /health stays public so
# the container healthcheck can run.
_RENDER_SERVICE_KEY = os.environ.get("RENDER_SERVICE_KEY", "")


def _require_key(auth_header: str | None) -> None:
    if not _RENDER_SERVICE_KEY:
        return
    if auth_header != _RENDER_SERVICE_KEY:
        raise HTTPException(status_code=401, detail="Invalid render key")


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
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--renderer-process-limit=1",
                    "--font-render-hinting=none",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--mute-audio",
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
async def render(
    req: RenderRequest,
    x_render_key: str | None = Header(default=None),
):
    """Render HTML to PNG and return image bytes."""
    _require_key(x_render_key)
    browser = await get_browser()
    page = await browser.new_page(viewport={"width": req.width, "height": req.height})

    try:
        await page.set_content(req.html, wait_until=req.wait_until)

        if req.wait_for_selector:
            try:
                await page.wait_for_selector(req.wait_for_selector, timeout=req.wait_for_timeout)
            except Exception:
                pass

        # Wait for webfonts to finish loading before capturing — otherwise
        # font-display:swap renders fallback fonts (e.g. Times New Roman).
        try:
            await page.evaluate("document.fonts.ready")
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
async def extract_dom(
    req: DOMExtractionRequest,
    x_render_key: str | None = Header(default=None),
):
    """Render HTML and extract the computed DOM tree with CSS properties."""
    _require_key(x_render_key)
    browser = await get_browser()
    page = await browser.new_page(viewport={"width": req.width, "height": req.height})

    try:
        await page.set_content(req.html, wait_until="networkidle")

        # Wait for webfonts so computed font families reflect the real faces.
        try:
            await page.evaluate("document.fonts.ready")
        except Exception:
            pass

        # JavaScript that walks the DOM and extracts computed styles + bounding boxes
        dom_tree = await page.evaluate("""({width, height}) => {
            // Tags considered inline (text-level semantics, NOT structural containers)
            const INLINE_TAGS = new Set([
                'span', 'strong', 'em', 'a', 'b', 'i', 'u', 's',
                'code', 'sub', 'sup', 'label', 'small', 'mark',
                'del', 'ins', 'q', 'abbr', 'cite', 'kbd', 'samp',
                'var', 'time', 'dfn',
            ]);

            function extractNode(el, parentX, parentY) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const tag = el.tagName ? el.tagName.toLowerCase() : 'text';

                // Skip elements with no size (collapsed, hidden, etc.)
                if (rect.width === 0 && rect.height === 0 && tag !== 'text') return null;
                if (style.display === 'none' || style.visibility === 'hidden') return null;

                // Check all children are inline elements
                const children = Array.from(el.children);
                const hasInlineChildren = children.length > 0 && children.every(
                    c => INLINE_TAGS.has(c.tagName.toLowerCase())
                );

                // Extract text content:
                //   - Single text node: use its textContent
                //   - Mixed inline children: use innerText (preserves full text across inline boundaries)
                //   - Otherwise: empty string
                let text = '';
                if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
                    text = el.childNodes[0].textContent.trim();
                } else if (hasInlineChildren || el.childNodes.length > 0) {
                    text = (el.innerText || '').trim();
                }

                // Parse per-side border properties
                const borderStyles = ['top', 'right', 'bottom', 'left'];
                const border = {};
                for (const side of borderStyles) {
                    border[side] = {
                        width: parseFloat(style[`border${side.charAt(0).toUpperCase() + side.slice(1)}Width`]) || 0,
                        color: style[`border${side.charAt(0).toUpperCase() + side.slice(1)}Color`] || 'transparent',
                        style: style[`border${side.charAt(0).toUpperCase() + side.slice(1)}Style`] || 'none',
                    };
                }

                // Parse box-shadow into its first shadow component (CSS supports comma-separated)
                const boxShadow = style.boxShadow && style.boxShadow !== 'none'
                    ? style.boxShadow.split(',')[0].trim()
                    : '';

                // Extract filter blur value if present
                const filterValue = style.filter && style.filter !== 'none' ? style.filter : '';

                // Parse per-corner border-radius (CSS shorthand may not expose all corners)
                const brTL = parseFloat(style.borderTopLeftRadius) || 0;
                const brTR = parseFloat(style.borderTopRightRadius) || 0;
                const brBR = parseFloat(style.borderBottomRightRadius) || 0;
                const brBL = parseFloat(style.borderBottomLeftRadius) || 0;

                // Detect gradient background for fill conversion
                const bgImage = style.backgroundImage || 'none';
                const hasGradient = bgImage.startsWith('linear-gradient') || bgImage.startsWith('radial-gradient');

                const node = {
                    tag: tag,
                    id: el.id || '',
                    classList: Array.from(el.classList || []),
                    text: text,
                    hasInlineChildren: hasInlineChildren,
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
                    // Per-corner border radius
                    borderTopLeftRadius: brTL,
                    borderTopRightRadius: brTR,
                    borderBottomRightRadius: brBR,
                    borderBottomLeftRadius: brBL,
                    opacity: parseFloat(style.opacity) || 1,
                    overflow: style.overflow,
                    // Background
                    backgroundImage: bgImage,
                    hasGradient: hasGradient,
                    // Per-side border
                    borderTopWidth: border.top.width,
                    borderRightWidth: border.right.width,
                    borderBottomWidth: border.bottom.width,
                    borderLeftWidth: border.left.width,
                    borderTopColor: border.top.color,
                    borderRightColor: border.right.color,
                    borderBottomColor: border.bottom.color,
                    borderLeftColor: border.left.color,
                    borderTopStyle: border.top.style,
                    borderRightStyle: border.right.style,
                    borderBottomStyle: border.bottom.style,
                    borderLeftStyle: border.left.style,
                    // Shadow & effects
                    boxShadow: boxShadow,
                    filter: filterValue,
                    backgroundImage: style.backgroundImage,
                    backgroundClip: style.backgroundClip,
                    // Children
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

                // Recursively process children.
                // Skip inline children (span, strong, etc.) — their text is included
                // in the parent's innerText; processing them as separate shapes would
                // create overlapping text layers.
                // EXCEPTION: .math and .diagram elements — they render as SVGs that
                // must be extracted as svg-raw shapes.
                for (const child of children) {
                    const childTag = child.tagName.toLowerCase();
                    const isMathOrDiagram = child.classList &&
                        (child.classList.contains('math') || child.classList.contains('diagram'));
                    if (INLINE_TAGS.has(childTag) && !isMathOrDiagram) continue;
                    const childNode = extractNode(child, rect.left, rect.top);
                    if (childNode) node.children.push(childNode);
                }

                // Extract pseudo-elements (::before, ::after) as synthetic children.
                // These are commonly used for decorative backgrounds, overlays, and accents.
                for (const pseudo of ['before', 'after']) {
                    const pStyle = window.getComputedStyle(el, `::${pseudo}`);
                    const pContent = pStyle.content || '';
                    // Pseudo-element exists when content is not "none"
                    if (pContent && pContent !== 'none' && pStyle.display !== 'none') {
                        // Detect text-only pseudo-elements (e.g. ::before { content: ">" }).
                        // These are rendered inline and can't be positioned as separate shapes.
                        // Skip them — the browser handles inline pseudo text natively.
                        const isTextOnly = !pStyle.backgroundImage
                            || pStyle.backgroundImage === 'none';
                        if (isTextOnly) continue;

                        // Pseudo-element position/size: use parent's rect as default
                        // (absolute-positioned pseudos are the most common use case)
                        const pWidth = parseFloat(pStyle.width) || rect.width;
                        const pHeight = parseFloat(pStyle.height) || rect.height;
                        const pTop = parseFloat(pStyle.top) || 0;
                        const pLeft = parseFloat(pStyle.left) || 0;
                        node.children.push({
                            tag: 'pseudo-' + pseudo,
                            id: '',
                            classList: [],
                            text: '',
                            hasInlineChildren: false,
                            pseudo: pseudo,
                            x: rect.left + pLeft,
                            y: rect.top + pTop,
                            width: isNaN(pWidth) ? rect.width : pWidth,
                            height: isNaN(pHeight) ? rect.height : pHeight,
                            backgroundColor: pStyle.backgroundColor,
                            color: pStyle.color,
                            fontFamily: 'inherit',
                            fontSize: 16,
                            fontWeight: '400',
                            lineHeight: 'normal',
                            letterSpacing: '0px',
                            textAlign: 'left',
                            borderRadius: pStyle.borderRadius,
                            borderTopLeftRadius: parseFloat(pStyle.borderTopLeftRadius) || 0,
                            borderTopRightRadius: parseFloat(pStyle.borderTopRightRadius) || 0,
                            borderBottomRightRadius: parseFloat(pStyle.borderBottomRightRadius) || 0,
                            borderBottomLeftRadius: parseFloat(pStyle.borderBottomLeftRadius) || 0,
                            opacity: parseFloat(pStyle.opacity) || 1,
                            overflow: 'visible',
                            borderTopWidth: parseFloat(pStyle.borderTopWidth) || 0,
                            borderRightWidth: parseFloat(pStyle.borderRightWidth) || 0,
                            borderBottomWidth: parseFloat(pStyle.borderBottomWidth) || 0,
                            borderLeftWidth: parseFloat(pStyle.borderLeftWidth) || 0,
                            borderTopColor: pStyle.borderTopColor || 'transparent',
                            borderRightColor: pStyle.borderRightColor || 'transparent',
                            borderBottomColor: pStyle.borderBottomColor || 'transparent',
                            borderLeftColor: pStyle.borderLeftColor || 'transparent',
                            borderTopStyle: pStyle.borderTopStyle || 'none',
                            borderRightStyle: pStyle.borderRightStyle || 'none',
                            borderBottomStyle: pStyle.borderBottomStyle || 'none',
                            borderLeftStyle: pStyle.borderLeftStyle || 'none',
                            boxShadow: pStyle.boxShadow && pStyle.boxShadow !== 'none'
                                ? pStyle.boxShadow.split(',')[0].trim()
                                : '',
                            filter: pStyle.filter && pStyle.filter !== 'none' ? pStyle.filter : '',
                            backgroundImage: pStyle.backgroundImage,
                            hasGradient: (pStyle.backgroundImage || '').startsWith('linear-gradient') || (pStyle.backgroundImage || '').startsWith('radial-gradient'),
                            backgroundClip: pStyle.backgroundClip || '',
                            children: [],
                            svgContent: null,
                        });
                    }
                }

                return node;
            }

            const body = document.body;
            return { dom: extractNode(body) };
        }""", {"width": req.width, "height": req.height})

        # Detect text elements overflowing the canvas (clipped by overflow:hidden).
        overflow = await page.evaluate("""() => {
            const vw = window.innerWidth, vh = window.innerHeight;
            const offenders = [];
            for (const el of document.querySelectorAll('*')) {
                if (el === document.body || el === document.documentElement) continue;
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                if (!(el.innerText || '').trim()) continue;
                if (rect.bottom > vh + 2 || rect.right > vw + 2) {
                    offenders.push({
                        tag: el.tagName.toLowerCase(),
                        cls: String(el.className || ''),
                        text: (el.innerText || '').trim().slice(0, 48),
                        overflowY: Math.round(rect.bottom - vh),
                        overflowX: Math.round(rect.right - vw),
                    });
                }
            }
            return offenders.slice(0, 10);
        }""")

        return {**dom_tree, "overflow": overflow}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await page.close()
