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
    'history': [],
    'circuit_breaker': False,
}


def read_json(filename: str, default=None):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path) as f:
        return json.load(f)


@app.get("/api/market")
def market(auth=Depends(require_auth)):
    return read_json("market_state.json")


@app.get("/api/portfolio")
def portfolio(auth=Depends(require_auth)):
    return read_json("portfolio.json", default=PORTFOLIO_DEFAULT)


@app.get("/api/trades")
def trades(auth=Depends(require_auth)):
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    with open(TRADE_LOG_FILE, newline='') as f:
        return list(csv.DictReader(f))


@app.get("/api/stream")
async def stream():
    async def event_generator():
        prev = None
        while True:
            market = read_json("market_state.json", default={})
            portfolio = read_json("portfolio.json", default=PORTFOLIO_DEFAULT)
            payload = {'market': market, 'portfolio': portfolio}
            if payload != prev:
                yield f"data: {json.dumps(payload)}\n\n"
                prev = payload
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
