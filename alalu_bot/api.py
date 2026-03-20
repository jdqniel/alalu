import csv
import json
import os
import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


def read_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


@app.get("/api/market")
def market(auth=Depends(require_auth)):
    return read_json("market_state.json")


@app.get("/api/portfolio")
def portfolio(auth=Depends(require_auth)):
    return read_json("portfolio.json")


@app.get("/api/trades")
def trades(auth=Depends(require_auth)):
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    with open(TRADE_LOG_FILE, newline='') as f:
        return list(csv.DictReader(f))
