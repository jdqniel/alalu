"""
Backtesting de la estrategia de momentum.

Uso:
    uv run python alalu_bot/backtest.py                        # BTC/USDT, 6 meses
    uv run python alalu_bot/backtest.py --symbol ETH/USDT --months 3
    uv run python alalu_bot/backtest.py --plot               # abre gráfico interactivo
"""
import argparse
from datetime import datetime, timedelta

import ccxt
import pandas as pd
from backtesting import Strategy
from backtesting.lib import FractionalBacktest as Backtest

# --- Mismos parámetros que engine.py ---
RIESGO_POR_TRADE = 100
ROC_PERIOD = 20
RSI_PERIOD = 14
ADX_PERIOD = 14
ATR_PERIOD = 14
HTF_EMA_PERIOD = 50

TRAILING_PCT = 0.015
INITIAL_SL_PCT = 0.015
TP_MULTIPLIER = 2.0

ADX_THRESH = 20
RSI_LONG_MIN = 50
RSI_LONG_MAX = 70
RSI_SHORT_MIN = 30
RSI_SHORT_MAX = 50
ROC_THRESH = 0.005

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
    adx = dx.ewm(com=period - 1, min_periods=period).mean()
    return adx, plus_di, minus_di


def _ema(series, period):
    return series.ewm(span=period, min_periods=period).mean()


# --- Fetch histórico ---

def fetch_ohlcv_df(symbol: str, timeframe: str, months: int) -> pd.DataFrame:
    exchange = ccxt.binance({'enableRateLimit': True})
    since = int((datetime.utcnow() - timedelta(days=30 * months)).timestamp() * 1000)
    all_bars = []
    while True:
        bars = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not bars:
            break
        all_bars.extend(bars)
        since = bars[-1][0] + 1
        if len(bars) < 1000:
            break

    df = pd.DataFrame(all_bars, columns=['ts', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    df.set_index('ts', inplace=True)
    df = df[~df.index.duplicated()]
    print(f"📊 {symbol} {timeframe}: {len(df)} velas ({months} meses)")
    return df


def fetch_htf_ema(symbol: str, timeframe: str = '1h', period: int = 50) -> pd.Series:
    exchange = ccxt.binance({'enableRateLimit': True})
    bars = exchange.fetch_ohlcv(symbol, timeframe, limit=period * 3)
    df = pd.DataFrame(bars, columns=['ts', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    df.set_index('ts', inplace=True)
    return _ema(df['Close'], period).resample('5min').ffill()


# --- Estrategia ---

class MomentumStrategy(Strategy):
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
        htf_ema = _ema(close.resample('1h').last().reindex(close.index, method='ffill'), HTF_EMA_PERIOD)

        self.rsi = self.I(lambda: rsi.values, name='RSI')
        self.adx = self.I(lambda: adx.values, name='ADX')
        self.plus_di = self.I(lambda: plus_di.values, name='+DI')
        self.minus_di = self.I(lambda: minus_di.values, name='-DI')
        self.roc = self.I(lambda: roc.values, name='ROC')
        self.vol = self.I(lambda: vol.values, name='Vol')
        self.vol_avg = self.I(lambda: vol_avg.values, name='VolAvg')
        self.atr = self.I(lambda: atr.values, name='ATR')
        self.htf_ema = self.I(lambda: htf_ema.values, name='HTF_EMA')

    def next(self):
        price = self.data.Close[-1]
        rsi = self.rsi[-1]
        adx = self.adx[-1]
        plus_di = self.plus_di[-1]
        minus_di = self.minus_di[-1]
        roc = self.roc[-1]
        vol = self.vol[-1]
        vol_avg = self.vol_avg[-1]
        atr = self.atr[-1]
        htf_ema = self.htf_ema[-1]

        import math
        if any(math.isnan(x) for x in [rsi, adx, roc, vol_avg, htf_ema]):
            return

        vol_surge = vol > vol_avg
        trending = adx > ADX_THRESH
        atr_pct = atr / price
        sl_distance = max(INITIAL_SL_PCT, atr_pct * 1.5)
        tp_distance = sl_distance * TP_MULTIPLIER

        htf_bullish = price > htf_ema
        htf_bearish = price < htf_ema

        # Session filter
        hour = self.data.index[-1].hour
        in_session = SESSION_START_UTC <= hour < SESSION_END_UTC

        long_signal = (
            trending and roc > ROC_THRESH
            and RSI_LONG_MIN < rsi < RSI_LONG_MAX
            and plus_di > minus_di and vol_surge and htf_bullish
        )
        short_signal = (
            trending and roc < -ROC_THRESH
            and RSI_SHORT_MIN < rsi < RSI_SHORT_MAX
            and minus_di > plus_di and vol_surge and htf_bearish
        )

        if self.position:
            return  # exits gestionados por sl/tp de backtesting.py

        if not in_session:
            return

        # Tamaño fijo: RIESGO_POR_TRADE como fracción del equity actual
        size = min(RIESGO_POR_TRADE / self.equity, 0.99)

        if long_signal:
            sl = price * (1 - sl_distance)
            tp = price * (1 + tp_distance)
            self.buy(size=size, sl=sl, tp=tp)
        elif short_signal:
            sl = price * (1 + sl_distance)
            tp = price * (1 - tp_distance)
            self.sell(size=size, sl=sl, tp=tp)


# --- Main ---

def run(symbol: str, months: int, plot: bool):
    print(f"\n{'='*50}")
    print(f"Backtesting: {symbol} | {months} meses | 5m")
    print(f"{'='*50}\n")

    df = fetch_ohlcv_df(symbol, '5m', months)

    bt = Backtest(
        df,
        MomentumStrategy,
        cash=400,
        commission=0.0004,
        exclusive_orders=True,
    )
    stats = bt.run()

    print(stats[['Start', 'End', 'Duration', 'Exposure Time [%]',
                  'Return [%]', 'Buy & Hold Return [%]', 'Max. Drawdown [%]',
                  'Win Rate [%]', '# Trades', 'Avg. Trade Duration',
                  'Profit Factor', 'Sharpe Ratio']].to_string())

    if plot:
        bt.plot()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='BTC/USDT')
    parser.add_argument('--months', type=int, default=6)
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    run(args.symbol, args.months, args.plot)
