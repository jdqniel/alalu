import ccxt
import pandas as pd
import json
import time
import os
import tempfile
from datetime import datetime

# --- CONFIG ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
CAPITAL_TOTAL = 400.0
RIESGO_POR_TRADE = 100.0
BINANCE_FEE = 0.001            # spot
BINANCE_FEE_FUTURES = 0.0004   # futures maker/taker promedio

ROC_PERIOD = 20
RSI_PERIOD = 14
ADX_PERIOD = 14
ATR_PERIOD = 14

TRAILING_PCT = 0.015        # 1.5% trailing stop
INITIAL_SL_PCT = 0.015      # stop mínimo (fallback si ATR es muy chico)
MAX_TRADE_MINUTES = 60      # salida por tiempo

ADX_THRESH = 25             # mínimo ADX para operar (mercado en tendencia)
RSI_LONG_MIN = 50           # RSI mínimo para long (momentum positivo)
RSI_LONG_MAX = 70           # RSI máximo para long (no sobrecomprado)
RSI_SHORT_MIN = 30          # RSI mínimo para short (no sobrevendido)
RSI_SHORT_MAX = 50          # RSI máximo para short (momentum negativo)
ROC_THRESH = 0.005          # 0.5% ROC mínimo para señal

MAX_CONCURRENT_TRADES = 2   # límite por correlación entre cripto
CIRCUIT_BREAKER_PCT = 0.80  # detener si balance 5x cae al 80%

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(DATA_DIR, 'market_state.json')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')

exchange = ccxt.binance()


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


def save_json(data, filepath):
    dir_name = os.path.dirname(os.path.abspath(filepath))
    with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, suffix='.tmp') as f:
        json.dump(data, f, default=str, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, filepath)


def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


def run_motor():
    if not os.path.exists(PORTFOLIO_FILE):
        portfolio = {
            'balance_1x': CAPITAL_TOTAL,
            'balance_5x': CAPITAL_TOTAL,
            'active_trades': {},
            'history': [],
            'circuit_breaker': False,
        }
    else:
        portfolio = load_json(PORTFOLIO_FILE)

    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"🚀 Motor de momentum iniciado. Data dir: {DATA_DIR}")

    while True:
        if portfolio.get('circuit_breaker'):
            print("🚨 Circuit breaker activo. Motor detenido.")
            time.sleep(60)
            continue

        if portfolio['balance_5x'] < CAPITAL_TOTAL * CIRCUIT_BREAKER_PCT:
            portfolio['circuit_breaker'] = True
            save_json(portfolio, PORTFOLIO_FILE)
            print(f"🚨 Circuit breaker activado: balance 5x = ${portfolio['balance_5x']:.2f}")
            continue

        market_snapshot = {}
        now = datetime.now()

        for symbol in SYMBOLS:
            try:
                bars = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=120)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])

                # --- INDICADORES ---
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

                # Stop dinámico basado en ATR (mínimo INITIAL_SL_PCT)
                sl_distance = max(INITIAL_SL_PCT, float(atr_pct) * 1.5)

                # --- SEÑALES DE MOMENTUM ---
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

                market_snapshot[symbol] = {
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

                # --- GESTIÓN DE TRADE ACTIVO ---
                if symbol in portfolio['active_trades']:
                    trade = portfolio['active_trades'][symbol]
                    direction = trade['direction']
                    entry = trade['entry_price']
                    pos = trade['position_usd']
                    sl_dist = trade['sl_distance']

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

                    entry_time = datetime.fromisoformat(trade['entry_time'])
                    minutes_elapsed = (now - entry_time).total_seconds() / 60
                    time_exit = minutes_elapsed >= MAX_TRADE_MINUTES

                    if exit_triggered or time_exit:
                        if is_liquidated:
                            gain_1x = -pos if direction == 'long' else 0
                            gain_5x = -pos
                            exit_reason = 'liquidation'
                        else:
                            fee_1x = pos * BINANCE_FEE * 2
                            fee_5x = (pos * 5) * BINANCE_FEE_FUTURES * 2
                            gain_1x = (pos * pnl_pct - fee_1x) if direction == 'long' else 0
                            gain_5x = pos * pnl_pct * 5 - fee_5x
                            if time_exit:
                                exit_reason = 'time_exit'
                            elif pnl_pct > 0:
                                exit_reason = 'trailing_stop'
                            else:
                                exit_reason = 'stop_loss'

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
                        del portfolio['active_trades'][symbol]
                        print(
                            f"{'💀' if is_liquidated else '🔚'} Exit {symbol} | {direction.upper()} | "
                            f"PnL 5x: ${gain_5x:.2f} | {exit_reason}"
                        )

                # --- ENTRADA ---
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
                        }
                        print(
                            f"📊 {signal.upper()} {symbol} @ {price:.4f} | "
                            f"SL={sl_price:.4f} | ADX={adx:.1f} | RSI={rsi:.1f} | ROC={roc*100:.2f}%"
                        )

            except Exception as e:
                print(f"Error {symbol}: {e}")

        save_json(market_snapshot, STATE_FILE)
        save_json(portfolio, PORTFOLIO_FILE)
        time.sleep(15)


if __name__ == "__main__":
    run_motor()
