import asyncio
import csv
import json
import os
import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()

ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
TRADE_LOG_FILE = os.path.join(DATA_DIR, 'trades.csv')

security = HTTPBasic(auto_error=False)
API_USER = os.environ.get('API_USER', '')
API_PASS = os.environ.get('API_PASS', '')


def require_auth(creds: HTTPBasicCredentials = Depends(security)):
    if not API_USER:
        return
    if creds is None:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    ok = (
        secrets.compare_digest(creds.username.encode(), API_USER.encode())
        and secrets.compare_digest(creds.password.encode(), API_PASS.encode())
    )
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


PORTFOLIO_DEFAULT = {
    'balance_1x': 400.0,
    'balance_5x': 400.0,
    'active_trades': {},
    'circuit_breaker': False,
}


def read_json(filename: str, default=None):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path) as f:
        return json.load(f)


# --- Cache de trades: solo re-lee el CSV si el archivo cambió ---
_trades_cache: list = []
_trades_mtime: float = 0.0


def read_trades() -> list:
    global _trades_cache, _trades_mtime
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    mtime = os.stat(TRADE_LOG_FILE).st_mtime
    if mtime == _trades_mtime:
        return _trades_cache
    with open(TRADE_LOG_FILE, newline='') as f:
        _trades_cache = list(csv.DictReader(f))
    _trades_mtime = mtime
    return _trades_cache


def _slim_portfolio(p: dict) -> dict:
    """Excluye history del payload SSE — el frontend usa el CSV."""
    return {k: v for k, v in p.items() if k != 'history'}


@app.get("/api/market")
def market(auth=Depends(require_auth)):
    return read_json("market_state.json")


@app.get("/api/portfolio")
def portfolio(auth=Depends(require_auth)):
    return read_json("portfolio.json", default=PORTFOLIO_DEFAULT)


@app.get("/api/trades")
def trades(auth=Depends(require_auth)):
    return read_trades()


@app.get("/api/stream")
async def stream(auth=Depends(require_auth)):
    async def event_generator():
        prev_sig: str | None = None
        while True:
            market = read_json("market_state.json", default={})
            portfolio = _slim_portfolio(
                read_json("portfolio.json", default=PORTFOLIO_DEFAULT)
            )
            trades = read_trades()
            payload = {'market': market, 'portfolio': portfolio, 'trades': trades}
            sig = json.dumps(payload, separators=(',', ':'))
            if sig != prev_sig:
                yield f"data: {sig}\n\n"
                prev_sig = sig
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
