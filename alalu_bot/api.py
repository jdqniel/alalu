import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))


def read_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


@app.get("/api/market")
def market():
    return read_json("market_state.json")


@app.get("/api/portfolio")
def portfolio():
    return read_json("portfolio.json")
