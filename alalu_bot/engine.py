import asyncio
import os
import json
import tempfile
from datetime import datetime

import ccxt.pro as ccxtpro
import pandas as pd

from notify import send
from trade_log import log_trade

# --- CONFIG ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
CAPITAL_TOTAL = 400.0
RIESGO_POR_TRADE = float(os.environ.get('RIESGO_POR_TRADE', '100'))
BINANCE_FEE = 0.001
BINANCE_FEE_FUTURES = 0.0004

ROC_PERIOD = 20
RSI_PERIOD = 14
ADX_PERIOD = 14
ATR_PERIOD = 14

TIMEFRAME = '5m'

TRAILING_PCT = 0.015
INITIAL_SL_PCT = 0.015
MAX_TRADE_MINUTES = 120

ADX_THRESH = 20
RSI_LONG_MIN = 50
RSI_LONG_MAX = 70
RSI_SHORT_MIN = 30
RSI_SHORT_MAX = 50
ROC_THRESH = 0.005

MAX_CONCURRENT_TRADES = 2
CIRCUIT_BREAKER_PCT = 0.80

LIVE_TRADING = os.environ.get('LIVE_TRADING', 'false').lower() == 'true'

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(DATA_DIR, 'market_state.json')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')


# --- INDICADORES ---

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))


def compute_atr(df, period=14):
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def compute_adx(df, period=14):
    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr = compute_atr(df, period)
    plus_di = 100 * plus_dm.ewm(com=period - 1, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(com=period - 1, min_periods=period).mean() / atr
    di_sum = (plus_di + minus_di).replace(0, float('nan'))
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx = dx.ewm(com=period - 1, min_periods=period).mean()
    return adx, plus_di, minus_di


def safe_float(val, multiplier=1, decimals=4):
    if pd.isna(val):
        return None
    return round(float(val) * multiplier, decimals)


# --- PERSISTENCIA ---

def save_json(data, filepath):
    dir_name = os.path.dirname(os.path.abspath(filepath))
    with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, suffix='.tmp') as f:
        json.dump(data, f, default=str, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, filepath)


def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return {
            'balance_1x': CAPITAL_TOTAL,
            'balance_5x': CAPITAL_TOTAL,
            'active_trades': {},
            'history': [],
            'circuit_breaker': False,
        }
    return load_json(PORTFOLIO_FILE)


# --- EJECUCIÓN DE ÓRDENES ---

async def execute_order(exchange, symbol, side, amount_usd, price):
    if not LIVE_TRADING:
        return {'id': 'paper', 'average': price}
    amount = amount_usd / price
    try:
        return await exchange.create_market_order(symbol, side, amount)
    except ccxtpro.InsufficientFunds:
        print(f"FONDOS INSUFICIENTES {symbol}")
        return None
    except ccxtpro.RateLimitExceeded:
        await asyncio.sleep(30)
        return None
    except Exception as e:
        print(f"ORDER ERROR {symbol}: {e}")
        return None


# --- RECONCILIACIÓN ---

async def reconcile_positions(exchange, portfolio):
    if not LIVE_TRADING:
        return portfolio
    try:
        balance = await exchange.fetch_balance()
        open_assets = {k for k, v in balance['total'].items() if v > 0.0001 and k != 'USDT'}
    except Exception as e:
        print(f"RECONCILE ERROR: {e}")
        return portfolio

    for symbol in list(portfolio['active_trades'].keys()):
        base = symbol.split('/')[0]
        if base not in open_assets:
            print(f"RECONCILE: {symbol} en dict pero no en exchange — limpiando")
            del portfolio['active_trades'][symbol]
    return portfolio


# --- EXITS EN TIEMPO REAL ---

def check_exits_realtime(symbol, price, portfolio):
    if symbol not in portfolio['active_trades']:
        return
    trade = portfolio['active_trades'][symbol]
    direction = trade['direction']
    entry = trade['entry_price']
    pos = trade['position_usd']
    sl_dist = trade['sl_distance']
    now = datetime.now()

    if direction == 'long':
        pnl_pct = (price - entry) / entry
        trade['highest_price'] = max(trade.get('highest_price', entry), price)
        trailing_stop = trade['highest_price'] * (1 - TRAILING_PCT)
        is_liquidated = pnl_pct <= -0.20
        exit_triggered = is_liquidated or price <= trailing_stop or pnl_pct <= -sl_dist
    else:
        pnl_pct = (entry - price) / entry
        trade['lowest_price'] = min(trade.get('lowest_price', entry), price)
        trailing_stop = trade['lowest_price'] * (1 + TRAILING_PCT)
        is_liquidated = pnl_pct <= -0.20
        exit_triggered = is_liquidated or price >= trailing_stop or pnl_pct <= -sl_dist

    if not exit_triggered:
        return

    entry_time = datetime.fromisoformat(trade['entry_time'])
    minutes_elapsed = (now - entry_time).total_seconds() / 60

    if is_liquidated:
        gain_1x = -pos if direction == 'long' else 0
        gain_5x = -pos
        exit_reason = 'liquidation'
    else:
        fee_1x = pos * BINANCE_FEE * 2
        fee_5x = (pos * 5) * BINANCE_FEE_FUTURES * 2
        gain_1x = (pos * pnl_pct - fee_1x) if direction == 'long' else 0
        gain_5x = pos * pnl_pct * 5 - fee_5x
        exit_reason = 'trailing_stop' if pnl_pct > 0 else 'stop_loss'

    portfolio['balance_1x'] += gain_1x
    portfolio['balance_5x'] += gain_5x

    history_entry = {
        'time': now.strftime("%H:%M"),
        'symbol': symbol,
        'direction': direction,
        'pnl_5x': round(gain_5x, 2),
        'duration_min': round(minutes_elapsed, 1),
        'exit_reason': exit_reason,
        'type': 'LIQ 💀' if is_liquidated else ('WIN ✅' if gain_5x > 0 else 'LOSS ❌'),
    }
    portfolio['history'].append(history_entry)

    log_trade({
        'symbol': symbol,
        'direction': direction,
        'entry_price': entry,
        'exit_price': price,
        'pnl_usd': round(gain_5x, 2),
        'pnl_pct': round(pnl_pct * 100, 3),
        'duration_min': round(minutes_elapsed, 1),
        'exit_reason': exit_reason,
        'order_id': trade.get('order_id', 'paper'),
    })

    send(f"🔚 Exit {symbol} | {direction.upper()} | PnL 5x: ${gain_5x:.2f} | {exit_reason}")
    print(f"{'💀' if is_liquidated else '🔚'} Exit {symbol} | {direction.upper()} | PnL 5x: ${gain_5x:.2f} | {exit_reason}")

    del portfolio['active_trades'][symbol]


# --- PROCESAMIENTO DE CANDLE CERRADA ---

def process_candle(symbol, buf, portfolio, market_state, exchange_ref):
    df = pd.DataFrame(buf[-120:], columns=['ts', 'open', 'high', 'low', 'close', 'vol'])

    df['rsi'] = compute_rsi(df['close'], RSI_PERIOD)
    df['atr'] = compute_atr(df, ATR_PERIOD)
    adx_s, plus_di_s, minus_di_s = compute_adx(df, ADX_PERIOD)
    df['adx'] = adx_s
    df['plus_di'] = plus_di_s
    df['minus_di'] = minus_di_s
    df['roc'] = df['close'].pct_change(ROC_PERIOD)
    df['vol_avg'] = df['vol'].rolling(20).mean()

    price = df['close'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    atr = df['atr'].iloc[-1]
    adx = df['adx'].iloc[-1]
    plus_di = df['plus_di'].iloc[-1]
    minus_di = df['minus_di'].iloc[-1]
    roc = df['roc'].iloc[-1]
    vol_surge = (
        not pd.isna(df['vol_avg'].iloc[-1])
        and df['vol'].iloc[-1] > df['vol_avg'].iloc[-1]
    )
    atr_pct = atr / price
    sl_distance = max(INITIAL_SL_PCT, float(atr_pct) * 1.5)

    trending = not pd.isna(adx) and adx > ADX_THRESH

    long_signal = (
        trending
        and not pd.isna(roc) and roc > ROC_THRESH
        and not pd.isna(rsi) and RSI_LONG_MIN < rsi < RSI_LONG_MAX
        and plus_di > minus_di
        and vol_surge
    )
    short_signal = (
        trending
        and not pd.isna(roc) and roc < -ROC_THRESH
        and not pd.isna(rsi) and RSI_SHORT_MIN < rsi < RSI_SHORT_MAX
        and minus_di > plus_di
        and vol_surge
    )

    now = datetime.now()
    market_state[symbol] = {
        'price': float(price),
        'roc': safe_float(roc, multiplier=100, decimals=3),
        'rsi': safe_float(rsi, decimals=1),
        'adx': safe_float(adx, decimals=1),
        'plus_di': safe_float(plus_di, decimals=1),
        'minus_di': safe_float(minus_di, decimals=1),
        'atr_pct': safe_float(atr_pct, multiplier=100, decimals=3),
        'signal': 'long' if long_signal else ('short' if short_signal else None),
        'timestamp': now.isoformat(),
    }

    # Evaluar time_exit en process_candle (no en tick)
    if symbol in portfolio['active_trades']:
        trade = portfolio['active_trades'][symbol]
        entry_time = datetime.fromisoformat(trade['entry_time'])
        minutes_elapsed = (now - entry_time).total_seconds() / 60
        if minutes_elapsed >= MAX_TRADE_MINUTES:
            direction = trade['direction']
            pos = trade['position_usd']
            entry = trade['entry_price']
            pnl_pct = (price - entry) / entry if direction == 'long' else (entry - price) / entry
            fee_1x = pos * BINANCE_FEE * 2
            fee_5x = (pos * 5) * BINANCE_FEE_FUTURES * 2
            gain_1x = (pos * pnl_pct - fee_1x) if direction == 'long' else 0
            gain_5x = pos * pnl_pct * 5 - fee_5x

            portfolio['balance_1x'] += gain_1x
            portfolio['balance_5x'] += gain_5x
            portfolio['history'].append({
                'time': now.strftime("%H:%M"),
                'symbol': symbol,
                'direction': direction,
                'pnl_5x': round(gain_5x, 2),
                'duration_min': round(minutes_elapsed, 1),
                'exit_reason': 'time_exit',
                'type': 'WIN ✅' if gain_5x > 0 else 'LOSS ❌',
            })
            log_trade({
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry,
                'exit_price': float(price),
                'pnl_usd': round(gain_5x, 2),
                'pnl_pct': round(pnl_pct * 100, 3),
                'duration_min': round(minutes_elapsed, 1),
                'exit_reason': 'time_exit',
                'order_id': trade.get('order_id', 'paper'),
            })
            send(f"⏱ Time exit {symbol} | {direction.upper()} | PnL 5x: ${gain_5x:.2f}")
            print(f"⏱ Time exit {symbol} | {direction.upper()} | PnL 5x: ${gain_5x:.2f}")
            del portfolio['active_trades'][symbol]

    # Entrada (solo si no hay trade activo en este symbol)
    elif len(portfolio['active_trades']) < MAX_CONCURRENT_TRADES:
        signal = 'long' if long_signal else ('short' if short_signal else None)
        if signal and portfolio['balance_5x'] >= RIESGO_POR_TRADE:
            sl_price = (
                price * (1 - sl_distance) if signal == 'long'
                else price * (1 + sl_distance)
            )
            portfolio['active_trades'][symbol] = {
                'entry_price': float(price),
                'entry_time': now.isoformat(),
                'direction': signal,
                'position_usd': RIESGO_POR_TRADE,
                'sl_distance': round(sl_distance, 4),
                'sl_price': round(float(sl_price), 4),
                'highest_price': float(price),
                'lowest_price': float(price),
                'order_id': 'paper',
            }
            send(f"📊 {signal.upper()} {symbol} @ {price:.4f} | SL={sl_price:.4f} | ADX={adx:.1f} | RSI={rsi:.1f}")
            print(
                f"📊 {signal.upper()} {symbol} @ {price:.4f} | "
                f"SL={sl_price:.4f} | ADX={adx:.1f} | RSI={rsi:.1f} | ROC={roc*100:.2f}%"
            )

    save_json(market_state, STATE_FILE)
    save_json(portfolio, PORTFOLIO_FILE)
    signal_str = market_state[symbol].get('signal') or '—'
    print(f"🕯 {symbol} @ {float(price):.2f} | RSI={safe_float(rsi, decimals=1)} ADX={safe_float(adx, decimals=1)} | {signal_str}")


# --- LOOPS ASYNC ---

async def watch_symbol_candles(exchange, symbol, portfolio, market_state, lock):
    # Bootstrap: obtener historial via REST antes de escuchar WS
    buf = []
    try:
        buf = await exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=120)
        print(f"📥 Bootstrap {symbol}: {len(buf)} velas")
    except Exception as e:
        print(f"Bootstrap error {symbol}: {e}")

    last_ts = buf[-1][0] if buf else 0

    while True:
        try:
            candles = await exchange.watch_ohlcv(symbol, TIMEFRAME)
            if not candles:
                continue
            # Actualizar buffer: reemplazar o agregar vela
            for candle in candles:
                if buf and candle[0] == buf[-1][0]:
                    buf[-1] = candle  # actualizar vela actual
                else:
                    buf.append(candle)  # nueva vela
            buf = buf[-120:]  # mantener solo últimas 120

            current_ts = buf[-1][0]
            if current_ts <= last_ts:
                continue
            last_ts = current_ts

            async with lock:
                if portfolio.get('circuit_breaker'):
                    continue
                if portfolio['balance_5x'] < CAPITAL_TOTAL * CIRCUIT_BREAKER_PCT:
                    portfolio['circuit_breaker'] = True
                    save_json(portfolio, PORTFOLIO_FILE)
                    send("🚨 Circuit breaker activado — bot detenido")
                    print(f"🚨 Circuit breaker activado: balance 5x = ${portfolio['balance_5x']:.2f}")
                    continue
                process_candle(symbol, buf, portfolio, market_state, exchange)
        except Exception as e:
            print(f"candle error {symbol}: {e}")
            await asyncio.sleep(5)


async def watch_symbol_ticker(exchange, symbol, portfolio, lock):
    while True:
        try:
            ticker = await exchange.watch_ticker(symbol)
            price = ticker.get('last')
            async with lock:
                if price and symbol in portfolio['active_trades']:
                    check_exits_realtime(symbol, float(price), portfolio)
        except Exception as e:
            print(f"ticker error {symbol}: {e}")
            await asyncio.sleep(5)


# --- MAIN ---

async def run_motor():
    os.makedirs(DATA_DIR, exist_ok=True)
    portfolio = load_portfolio()
    market_state = {}
    lock = asyncio.Lock()

    config = {}
    if LIVE_TRADING:
        config['apiKey'] = os.environ['BINANCE_API_KEY']
        config['secret'] = os.environ['BINANCE_SECRET']
        config['options'] = {
            'sandboxMode': os.environ.get('BINANCE_SANDBOX', 'false').lower() == 'true'
        }

    exchange = ccxtpro.binance(config)
    print(f"🚀 Motor iniciado. LIVE_TRADING={LIVE_TRADING}. Data dir: {DATA_DIR}")

    try:
        portfolio = await reconcile_positions(exchange, portfolio)
        await asyncio.gather(
            *[watch_symbol_candles(exchange, s, portfolio, market_state, lock) for s in SYMBOLS],
            *[watch_symbol_ticker(exchange, s, portfolio, lock) for s in SYMBOLS],
        )
    except KeyboardInterrupt:
        pass
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(run_motor())
