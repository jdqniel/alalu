import asyncio
import logging
import os
import json
import tempfile
from datetime import datetime, timezone

import ccxt.pro as ccxtpro
import pandas as pd

from notify import send
from trade_log import log_trade

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('alalu')

# --- CONFIG ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT']
CAPITAL_TOTAL = 400.0
RIESGO_POR_TRADE = float(os.environ.get('RIESGO_POR_TRADE', '100'))
BINANCE_FEE = 0.001
BINANCE_FEE_FUTURES = 0.0004

ROC_PERIOD = 20
RSI_PERIOD = 14
ADX_PERIOD = 14
ATR_PERIOD = 14
HTF_EMA_PERIOD = 50

TIMEFRAME = '5m'
HTF_TIMEFRAME = '1h'

TRAILING_PCT = 0.015
INITIAL_SL_PCT = 0.015
TP_MULTIPLIER = 3.0          # take profit = sl_distance * 3 (optimizado)
MAX_TRADE_MINUTES = 120

ADX_THRESH = 25              # optimizado (era 20)
RSI_LONG_MIN = 52            # optimizado (era 50)
RSI_LONG_MAX = 70
RSI_SHORT_MIN = 30
RSI_SHORT_MAX = 50
ROC_THRESH = 0.005

MAX_CONCURRENT_TRADES = 2
CIRCUIT_BREAKER_PCT = 0.80

SESSION_START_UTC = 13       # 13:00 UTC — apertura NY
SESSION_END_UTC = 21         # 21:00 UTC — cierre EU

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


def compute_ema(series, period):
    return series.ewm(span=period, min_periods=period).mean()


def safe_float(val, multiplier=1, decimals=4):
    if pd.isna(val):
        return None
    return round(float(val) * multiplier, decimals)


def in_session() -> bool:
    hour = datetime.now(timezone.utc).hour
    return SESSION_START_UTC <= hour < SESSION_END_UTC


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
        log.error(f"FONDOS INSUFICIENTES {symbol}")
        return None
    except ccxtpro.RateLimitExceeded:
        await asyncio.sleep(30)
        return None
    except Exception as e:
        log.error(f"ORDER ERROR {symbol}: {e}")
        return None


# --- RECONCILIACIÓN ---

async def reconcile_positions(exchange, portfolio):
    if not LIVE_TRADING:
        return portfolio
    try:
        balance = await exchange.fetch_balance()
        open_assets = {k for k, v in balance['total'].items() if v > 0.0001 and k != 'USDT'}
    except Exception as e:
        log.warning(f"RECONCILE ERROR: {e}")
        return portfolio

    for symbol in list(portfolio['active_trades'].keys()):
        base = symbol.split('/')[0]
        if base not in open_assets:
            log.warning(f"RECONCILE: {symbol} en dict pero no en exchange — limpiando")
            del portfolio['active_trades'][symbol]
    return portfolio


# --- EXITS EN TIEMPO REAL ---

def _close_trade(symbol, price, portfolio, exit_reason, is_liquidated=False):
    trade = portfolio['active_trades'][symbol]
    direction = trade['direction']
    entry = trade['entry_price']
    pos = trade['position_usd']
    now = datetime.now()
    entry_time = datetime.fromisoformat(trade['entry_time'])
    minutes_elapsed = (now - entry_time).total_seconds() / 60

    if direction == 'long':
        pnl_pct = (price - entry) / entry
    else:
        pnl_pct = (entry - price) / entry

    if is_liquidated:
        gain_1x = -pos if direction == 'long' else 0
        gain_5x = -pos
    else:
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
        'exit_reason': exit_reason,
        'type': 'LIQ 💀' if is_liquidated else ('WIN ✅' if gain_5x > 0 else 'LOSS ❌'),
    })
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
    emoji = '💀' if is_liquidated else ('🎯' if exit_reason == 'take_profit' else '🔚')
    send(f"{emoji} Exit {symbol} | {direction.upper()} | PnL 5x: ${gain_5x:.2f} | {exit_reason}")
    log.info(f"{emoji} Exit {symbol} | {direction.upper()} | PnL 5x: ${gain_5x:.2f} | {exit_reason}")
    del portfolio['active_trades'][symbol]


def check_exits_realtime(symbol, price, portfolio):
    if symbol not in portfolio['active_trades']:
        return
    trade = portfolio['active_trades'][symbol]
    direction = trade['direction']
    entry = trade['entry_price']
    sl_dist = trade['sl_distance']
    tp_price = trade.get('tp_price')

    if direction == 'long':
        pnl_pct = (price - entry) / entry
        trade['highest_price'] = max(trade.get('highest_price', entry), price)
        trailing_stop = trade['highest_price'] * (1 - TRAILING_PCT)
        is_liquidated = pnl_pct <= -0.20
        if tp_price and price >= tp_price:
            _close_trade(symbol, price, portfolio, 'take_profit')
            return
        if is_liquidated or price <= trailing_stop or pnl_pct <= -sl_dist:
            _close_trade(symbol, price, portfolio, 'liquidation' if is_liquidated else ('trailing_stop' if pnl_pct > 0 else 'stop_loss'), is_liquidated)
    else:
        pnl_pct = (entry - price) / entry
        trade['lowest_price'] = min(trade.get('lowest_price', entry), price)
        trailing_stop = trade['lowest_price'] * (1 + TRAILING_PCT)
        is_liquidated = pnl_pct <= -0.20
        if tp_price and price <= tp_price:
            _close_trade(symbol, price, portfolio, 'take_profit')
            return
        if is_liquidated or price >= trailing_stop or pnl_pct <= -sl_dist:
            _close_trade(symbol, price, portfolio, 'liquidation' if is_liquidated else ('trailing_stop' if pnl_pct > 0 else 'stop_loss'), is_liquidated)


# --- PROCESAMIENTO DE CANDLE CERRADA ---

def process_candle(symbol, buf, portfolio, market_state, htf_cache, exchange_ref):
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

    # Filtro HTF: solo operar en dirección de la tendencia en 1h
    htf_ema = htf_cache.get(symbol)
    htf_bullish = htf_ema is not None and float(price) > htf_ema
    htf_bearish = htf_ema is not None and float(price) < htf_ema

    trending = not pd.isna(adx) and adx > ADX_THRESH

    long_signal = (
        trending
        and not pd.isna(roc) and roc > ROC_THRESH
        and not pd.isna(rsi) and RSI_LONG_MIN < rsi < RSI_LONG_MAX
        and plus_di > minus_di
        and vol_surge
        and htf_bullish
    )
    short_signal = (
        trending
        and not pd.isna(roc) and roc < -ROC_THRESH
        and not pd.isna(rsi) and RSI_SHORT_MIN < rsi < RSI_SHORT_MAX
        and minus_di > plus_di
        and vol_surge
        and htf_bearish
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
        'htf_ema': round(htf_ema, 2) if htf_ema else None,
        'htf_trend': 'bull' if htf_bullish else ('bear' if htf_bearish else None),
        'signal': 'long' if long_signal else ('short' if short_signal else None),
        'timestamp': now.isoformat(),
    }

    # Time exit
    if symbol in portfolio['active_trades']:
        trade = portfolio['active_trades'][symbol]
        entry_time = datetime.fromisoformat(trade['entry_time'])
        minutes_elapsed = (now - entry_time).total_seconds() / 60
        if minutes_elapsed >= MAX_TRADE_MINUTES:
            _close_trade(symbol, float(price), portfolio, 'time_exit')

    # Entrada: solo en sesión activa y sin trade abierto en este symbol
    elif len(portfolio['active_trades']) < MAX_CONCURRENT_TRADES:
        signal = 'long' if long_signal else ('short' if short_signal else None)
        if signal and portfolio['balance_5x'] >= RIESGO_POR_TRADE and in_session():
            sl_price = (
                price * (1 - sl_distance) if signal == 'long'
                else price * (1 + sl_distance)
            )
            tp_price = (
                price * (1 + sl_distance * TP_MULTIPLIER) if signal == 'long'
                else price * (1 - sl_distance * TP_MULTIPLIER)
            )
            portfolio['active_trades'][symbol] = {
                'entry_price': float(price),
                'entry_time': now.isoformat(),
                'direction': signal,
                'position_usd': RIESGO_POR_TRADE,
                'sl_distance': round(sl_distance, 4),
                'sl_price': round(float(sl_price), 4),
                'tp_price': round(float(tp_price), 4),
                'highest_price': float(price),
                'lowest_price': float(price),
                'order_id': 'paper',
            }
            send(
                f"📊 {signal.upper()} {symbol} @ {price:.4f} | "
                f"SL={sl_price:.4f} TP={tp_price:.4f} | ADX={adx:.1f} | RSI={rsi:.1f}"
            )
            log.info(
                f"📊 {signal.upper()} {symbol} @ {price:.4f} | "
                f"SL={sl_price:.4f} TP={tp_price:.4f} | ADX={adx:.1f} | RSI={rsi:.1f} | ROC={roc*100:.2f}%"
            )
        elif signal and not in_session():
            log.info(f"⏸ Señal {signal.upper()} {symbol} fuera de sesión — ignorada")

    save_json(market_state, STATE_FILE)
    save_json(portfolio, PORTFOLIO_FILE)
    htf_str = f"HTF={'▲' if htf_bullish else '▼'}" if htf_ema else "HTF=—"
    signal_str = market_state[symbol].get('signal') or '—'
    log.info(f"🕯 {symbol} @ {float(price):.2f} | RSI={safe_float(rsi, decimals=1)} ADX={safe_float(adx, decimals=1)} | {htf_str} | {signal_str}")


# --- LOOPS ASYNC ---

async def watch_symbol_candles(exchange, symbol, portfolio, market_state, htf_cache, lock):
    buf = []
    try:
        buf = await exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=120)
        log.info(f"📥 Bootstrap {symbol}: {len(buf)} velas {TIMEFRAME}")
    except Exception as e:
        log.info(f"Bootstrap error {symbol}: {e}")

    last_ts = buf[-1][0] if buf else 0

    while True:
        try:
            candles = await exchange.watch_ohlcv(symbol, TIMEFRAME)
            if not candles:
                continue
            for candle in candles:
                if buf and candle[0] == buf[-1][0]:
                    buf[-1] = candle
                else:
                    buf.append(candle)
            buf = buf[-120:]

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
                    log.warning(f"🚨 Circuit breaker activado: balance 5x = ${portfolio['balance_5x']:.2f}")
                    continue
                process_candle(symbol, buf, portfolio, market_state, htf_cache, exchange)
        except Exception as e:
            log.error(f"candle error {symbol}: {e}")
            await asyncio.sleep(5)


async def watch_symbol_htf(exchange, symbol, htf_cache, lock):
    buf = []
    try:
        buf = await exchange.fetch_ohlcv(symbol, HTF_TIMEFRAME, limit=60)
        df = pd.DataFrame(buf, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        ema = compute_ema(df['close'], HTF_EMA_PERIOD).iloc[-1]
        async with lock:
            htf_cache[symbol] = float(ema)
        log.info(f"📥 Bootstrap HTF {symbol}: EMA{HTF_EMA_PERIOD}={ema:.2f}")
    except Exception as e:
        log.info(f"Bootstrap HTF error {symbol}: {e}")

    last_ts = buf[-1][0] if buf else 0

    while True:
        try:
            candles = await exchange.watch_ohlcv(symbol, HTF_TIMEFRAME)
            if not candles:
                continue
            for candle in candles:
                if buf and candle[0] == buf[-1][0]:
                    buf[-1] = candle
                else:
                    buf.append(candle)
            buf = buf[-60:]

            current_ts = buf[-1][0]
            if current_ts <= last_ts:
                continue
            last_ts = current_ts

            df = pd.DataFrame(buf, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            ema = compute_ema(df['close'], HTF_EMA_PERIOD).iloc[-1]
            async with lock:
                htf_cache[symbol] = float(ema)
            log.info(f"📡 HTF {symbol}: EMA{HTF_EMA_PERIOD}={ema:.2f}")
        except Exception as e:
            log.error(f"htf error {symbol}: {e}")
            await asyncio.sleep(30)


async def watch_symbol_ticker(exchange, symbol, portfolio, lock):
    while True:
        try:
            ticker = await exchange.watch_ticker(symbol)
            price = ticker.get('last')
            async with lock:
                if price and symbol in portfolio['active_trades']:
                    check_exits_realtime(symbol, float(price), portfolio)
        except Exception as e:
            log.error(f"ticker error {symbol}: {e}")
            await asyncio.sleep(5)


# --- MAIN ---

async def run_motor():
    os.makedirs(DATA_DIR, exist_ok=True)
    portfolio = load_portfolio()
    market_state = {}
    htf_cache = {}
    lock = asyncio.Lock()

    config = {}
    if LIVE_TRADING:
        config['apiKey'] = os.environ['BINANCE_API_KEY']
        config['secret'] = os.environ['BINANCE_SECRET']
        config['options'] = {
            'sandboxMode': os.environ.get('BINANCE_SANDBOX', 'false').lower() == 'true'
        }

    exchange = ccxtpro.binance(config)
    log.info(f"🚀 Motor iniciado. LIVE_TRADING={LIVE_TRADING}. Sesión: {SESSION_START_UTC}-{SESSION_END_UTC} UTC. Data dir: {DATA_DIR}")

    try:
        portfolio = await reconcile_positions(exchange, portfolio)
        await asyncio.gather(
            *[watch_symbol_candles(exchange, s, portfolio, market_state, htf_cache, lock) for s in SYMBOLS],
            *[watch_symbol_htf(exchange, s, htf_cache, lock) for s in SYMBOLS],
            *[watch_symbol_ticker(exchange, s, portfolio, lock) for s in SYMBOLS],
        )
    except KeyboardInterrupt:
        pass
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(run_motor())
