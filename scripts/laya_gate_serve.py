#!/usr/bin/env python3
"""Local Laya gate service: single `needs_web` decision before LLM calls.

SHADOW/OBSERVATIONAL (2026-10-02 metric revision): the pilot acceptance
thresholds were NOT met on the corrected metrics (test acc 0.80, high-conf
failure 0.08, n=25; wiki/system-one-olcum-plani.md). The decision must not
gate or hide any tool; callers treat it as a signal only and stay fail-open.
The service returns probabilities; caller-side policy decides what to do.

Run:  .venv/bin/python scripts/laya_gate_serve.py   (binds 127.0.0.1:8791)
Test: curl -s localhost:8791/health
      curl -s localhost:8791/gate -H 'content-type: application/json' \
           -d '{"text": "pydantic 3 breaking changeleri araştır"}'
"""
import os
import time
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = os.environ.get("LAYA_GATE_MODEL", str(REPO_ROOT / "models" / "laya-ft"))
HOST = os.environ.get("LAYA_GATE_HOST", "127.0.0.1")
PORT = int(os.environ.get("LAYA_GATE_PORT", "8791"))

QUESTION = {
    "type": "noul",
    "instructions": (
        "Does completing this task require fetching current external information "
        "from the web (search, docs, benchmarks, news)? Lookups limited to the "
        "local repository or local knowledge base do not count."
    ),
}

app = FastAPI(title="noma-laya-gate")
_router = None
_load_error = None


def get_router():
    global _router, _load_error
    if _router is None and _load_error is None:
        try:
            from laya import Router
            _router = Router(models={"multilingual": MODEL_DIR},
                             preload=["multilingual"], max_loaded=1, device="mps")
        except Exception as exc:  # fail-open: report, never crash the loop
            _load_error = f"{type(exc).__name__}: {exc}"
    return _router


class GateRequest(BaseModel):
    text: str


@app.get("/health")
def health():
    return {
        "status": "ok" if _router is not None else ("error" if _load_error else "loading"),
        "model": MODEL_DIR,
        "question": "needs_web",
        "detail": _load_error,
    }


@app.post("/gate")
def gate(req: GateRequest):
    router = get_router()
    if router is None:
        return {"decision": "unknown", "p": None, "latency_ms": None,
                "reason": "model unavailable (fail-open)"}
    t0 = time.perf_counter()
    try:
        r = router.predict(req.text, {"needs_web": QUESTION}, model="multilingual")
    except Exception as exc:
        return {"decision": "unknown", "p": None,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "reason": f"predict failed (fail-open): {type(exc).__name__}"}
    p = float(r["answers"]["needs_web"]["noul"])
    return {
        "decision": "needs_web" if p >= 0.5 else "local_ok",
        "p": round(p, 4),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


if __name__ == "__main__":
    import uvicorn
    get_router()  # warm load before accepting traffic
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
