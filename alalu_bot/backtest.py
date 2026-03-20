"""
Backtesting y optimización de la estrategia de momentum.

Uso:
    uv run python alalu_bot/backtest.py                   # BTC/USDT, 6 meses
    uv run python alalu_bot/backtest.py --symbol ETH/USDT --months 3
    uv run python alalu_bot/backtest.py --optimize        # grid search de parámetros
    uv run python alalu_bot/backtest.py --plot            # gráfico interactivo
"""
import argparse
import math
import resource
import warnings
from datetime import datetime, timedelta, timezone

# macOS limita file descriptors a 256 por defecto — multiprocessing los agota
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
except Exception:
    pass

import ccxt
import pandas as pd
from backtesting import Strategy
from backtesting.lib import FractionalBacktest as Backtest

warnings.filterwarnings('ignore')

# --- Parámetros base (mismos que engine.py) ---
RIESGO_POR_TRADE = 100
ROC_PERIOD = 20
RSI_PERIOD = 14
ADX_PERIOD = 14
ATR_PERIOD = 14
HTF_EMA_PERIOD = 50

INITIAL_SL_PCT = 0.015
SESSION_START_UTC = 13
SESSION_END_UTC = 21


# --- Indicadores ---

def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))


def _atr(df, period=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def _adx(df, period=14):
    up = df['High'].diff()
    down = -df['Low'].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr = _atr(df, period)
    plus_di = 100 * plus_dm.ewm(com=period - 1, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(com=period - 1, min_periods=period).mean() / atr
    di_sum = (plus_di + minus_di).replace(0, float('nan'))
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    return dx.ewm(com=period - 1, min_periods=period).mean(), plus_di, minus_di


def _ema(series, period):
    return series.ewm(span=period, min_periods=period).mean()


# --- Fetch histórico ---

def fetch_ohlcv_df(symbol: str, months: int, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    exchange = ccxt.binance({'enableRateLimit': True})

    if start:
        since = int(datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)
    else:
        since = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)

    end_ms = None
    if end:
        end_ms = int(datetime.strptime(end, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)

    all_bars = []
    while True:
        bars = exchange.fetch_ohlcv(symbol, '5m', since=since, limit=1000)
        if not bars:
            break
        if end_ms:
            bars = [b for b in bars if b[0] <= end_ms]
        all_bars.extend(bars)
        if len(bars) < 1000 or (end_ms and bars[-1][0] >= end_ms):
            break
        since = bars[-1][0] + 1

    df = pd.DataFrame(all_bars, columns=['ts', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    df.set_index('ts', inplace=True)
    df = df[~df.index.duplicated()]
    label = f"{start} → {end}" if start else f"{months} meses"
    print(f"📊 {symbol} 5m: {len(df)} velas ({label})")
    return df


# --- Estrategia con parámetros optimizables ---

class MomentumStrategy(Strategy):
    # Parámetros optimizables (class-level para bt.optimize)
    adx_thresh = 20
    rsi_long_min = 50
    rsi_long_max = 70
    roc_thresh_bp = 5      # en basis points: 5 = 0.5%, 8 = 0.8%
    tp_mult_x10 = 20       # multiplicado x10: 20 = 2.0x, 25 = 2.5x

    def init(self):
        close = pd.Series(self.data.Close, index=self.data.df.index)
        high = pd.Series(self.data.High, index=self.data.df.index)
        low = pd.Series(self.data.Low, index=self.data.df.index)
        vol = pd.Series(self.data.Volume, index=self.data.df.index)
        df = pd.DataFrame({'High': high, 'Low': low, 'Close': close, 'Volume': vol})

        rsi = _rsi(close, RSI_PERIOD)
        atr = _atr(df, ATR_PERIOD)
        adx, plus_di, minus_di = _adx(df, ADX_PERIOD)
        roc = close.pct_change(ROC_PERIOD)
        vol_avg = vol.rolling(20).mean()
        htf_ema = _ema(
            close.resample('1h').last().reindex(close.index, method='ffill'),
            HTF_EMA_PERIOD,
        )

        self._rsi = self.I(lambda: rsi.values, name='RSI', overlay=False)
        self._adx = self.I(lambda: adx.values, name='ADX', overlay=False)
        self._plus_di = self.I(lambda: plus_di.values, name='+DI', overlay=False)
        self._minus_di = self.I(lambda: minus_di.values, name='-DI', overlay=False)
        self._roc = self.I(lambda: roc.values, name='ROC', overlay=False)
        self._vol = self.I(lambda: vol.values, name='Vol', overlay=False)
        self._vol_avg = self.I(lambda: vol_avg.values, name='VolAvg', overlay=False)
        self._atr = self.I(lambda: atr.values, name='ATR', overlay=False)
        self._htf_ema = self.I(lambda: htf_ema.values, name='HTF_EMA', overlay=True)

    def next(self):
        price = self.data.Close[-1]
        rsi = self._rsi[-1]
        adx = self._adx[-1]
        plus_di = self._plus_di[-1]
        minus_di = self._minus_di[-1]
        roc = self._roc[-1]
        vol = self._vol[-1]
        vol_avg = self._vol_avg[-1]
        atr = self._atr[-1]
        htf_ema = self._htf_ema[-1]

        if any(math.isnan(x) for x in [rsi, adx, roc, vol_avg, htf_ema]):
            return

        roc_thresh = self.roc_thresh_bp / 1000
        tp_multiplier = self.tp_mult_x10 / 10

        vol_surge = vol > vol_avg
        trending = adx > self.adx_thresh
        atr_pct = atr / price
        sl_distance = max(INITIAL_SL_PCT, atr_pct * 1.5)

        htf_bullish = price > htf_ema
        htf_bearish = price < htf_ema

        hour = self.data.index[-1].hour
        in_session = SESSION_START_UTC <= hour < SESSION_END_UTC

        long_signal = (
            trending and roc > roc_thresh
            and self.rsi_long_min < rsi < self.rsi_long_max
            and plus_di > minus_di and vol_surge and htf_bullish
        )
        short_signal = (
            trending and roc < -roc_thresh
            and 100 - self.rsi_long_max < rsi < 100 - self.rsi_long_min
            and minus_di > plus_di and vol_surge and htf_bearish
        )

        if self.position or not in_session:
            return

        size = min(RIESGO_POR_TRADE / self.equity, 0.99)

        if long_signal:
            self.buy(size=size, sl=price * (1 - sl_distance), tp=price * (1 + sl_distance * tp_multiplier))
        elif short_signal:
            self.sell(size=size, sl=price * (1 + sl_distance), tp=price * (1 - sl_distance * tp_multiplier))


# --- Main ---

def run(symbol: str, months: int, plot: bool, optimize: bool, start: str | None = None, end: str | None = None):
    label = f"{start} → {end}" if start else f"{months} meses"
    print(f"\n{'='*55}")
    print(f"  {'Optimización' if optimize else 'Backtest'}: {symbol} | {label} | 5m")
    print(f"{'='*55}\n")

    df = fetch_ohlcv_df(symbol, months, start=start, end=end)

    bt = Backtest(df, MomentumStrategy, cash=400, commission=0.0004, exclusive_orders=True)

    if optimize:
        print("🔍 Corriendo grid search... (puede tardar 2-5 min)\n")
        stats, heatmap = bt.optimize(
            adx_thresh=[18, 20, 22, 25],
            rsi_long_min=[48, 50, 52, 55],
            roc_thresh_bp=[4, 5, 7, 10],
            tp_mult_x10=[15, 20, 25, 30],
            maximize='Profit Factor',
            return_heatmap=True,
        )
        print("🏆 Mejores parámetros encontrados:")
        print(f"   adx_thresh    = {stats._strategy.adx_thresh}")
        print(f"   rsi_long_min  = {stats._strategy.rsi_long_min}")
        print(f"   roc_thresh    = {stats._strategy.roc_thresh_bp / 1000:.3f} ({stats._strategy.roc_thresh_bp} bp)")
        print(f"   tp_multiplier = {stats._strategy.tp_mult_x10 / 10:.1f}x")
        print()
    else:
        stats = bt.run()

    cols = [
        'Return [%]', 'Buy & Hold Return [%]', 'Max. Drawdown [%]',
        'Win Rate [%]', '# Trades', 'Avg. Trade Duration',
        'Profit Factor', 'Sharpe Ratio', 'Exposure Time [%]',
    ]
    print(stats[cols].to_string())

    if plot:
        bt.plot()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='BTC/USDT')
    parser.add_argument('--months', type=int, default=6)
    parser.add_argument('--start', default=None, help='Fecha inicio YYYY-MM-DD (override --months)')
    parser.add_argument('--end', default=None, help='Fecha fin YYYY-MM-DD (default: hoy)')
    parser.add_argument('--optimize', action='store_true')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    run(args.symbol, args.months, args.plot, args.optimize, start=args.start, end=args.end)
