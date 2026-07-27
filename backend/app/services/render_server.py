"""Playwright HTTP microservice — stub for Phase 4 DOM extraction.

Will be properly implemented during Phase 4 for the HTML->Penpot converter.
For now, it just confirms the service is alive.
"""

from fastapi import FastAPI

app = FastAPI(title="Playwright DOM Extraction Service (stub)")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "playwright-dom-extraction", "phase": "stub"}
