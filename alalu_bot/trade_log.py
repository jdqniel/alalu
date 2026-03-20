import csv
import os
from datetime import datetime

TRADE_LOG_FILE = os.path.join(os.environ.get('DATA_DIR', '.'), 'trades.csv')
HEADERS = [
    'timestamp', 'symbol', 'direction', 'entry_price', 'exit_price',
    'pnl_usd', 'pnl_pct', 'duration_min', 'exit_reason', 'order_id',
]


def log_trade(trade_dict: dict):
    exists = os.path.exists(TRADE_LOG_FILE)
    with open(TRADE_LOG_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, extrasaction='ignore')
        if not exists:
            writer.writeheader()
        writer.writerow({**trade_dict, 'timestamp': datetime.now().isoformat()})
