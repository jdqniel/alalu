# Fase 1: Backtest de reversión a la media con Z-Score + EMA 200 (BTC/USDT 5m)
# Hipótesis: si el precio se desvía demasiado de su media (Z extremo) pero
# la tendencia macro es alcista (precio > EMA 200), debería revertir.
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

exchange = ccxt.binance()

short_window = 20
long_window = 200
fee = 0.001

bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='5m')
df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

df['ema_200'] = df['close'].ewm(span=long_window, adjust=False).mean()
df['mean_20'] = df['close'].rolling(window=short_window).mean()
df['std_20'] = df['close'].rolling(window=short_window).std()
df['z_score'] = (df['close'] - df['mean_20']) / df['std_20']

df['signal'] = np.where((df['close'] > df['ema_200']) & (df['z_score'] < -3), 'BUY', 
                        np.where((df['close'] < df['ema_200']) & (df['z_score'] > 3), 'SELL', 'HOLD'))
# print(df[['close', 'ema_200', 'z_score', 'signal']].tail())  # exploración inicial

df['market_return'] = df['close'].pct_change()

df['position'] = df['signal'].replace({'BUY': 1, 'SELL': -1, 'HOLD':0}).shift(1)
df['position'] = pd.to_numeric(df['position'].fillna(0))

df['strategy_return'] = df['position'] * df['market_return']

df['cumulative_market'] = (1 + df['market_return']).cumprod()
df['cumulative_strategy'] = (1 + df['strategy_return']).cumprod()

df['trades'] = df['position'].diff().fillna(0).abs()

df['strategy_net_return'] = df['strategy_return'] - (df['trades'] * fee)

df['cumulative_strategy_net'] = (1 + df['strategy_net_return']).cumprod()

print(f"Retorno Neto (Después de Comisiones): {(df['cumulative_strategy_net'].iloc[-1] - 1) * 100:.2f}%")
# print(f"Retorno Total Mercado: {(df['cumulative_market'].iloc[-1] - 1) * 100:.2f}%")
# print(f"Retorno Total Estrategia: {(df['cumulative_strategy'].iloc[-1] - 1) * 100:.2f}%")
# plt.figure(figsize=(12,6))
# plt.plot(df['timestamp'], df['z_score'], label='Z_score', color = 'blue')
#
# plt.axhline(y=2, color='red', linestyle='--', label='Venta (Overbought)')
# plt.axhline(y=-2, color='green', linestyle='--', label='Compra (Oversold)')
# plt.axhline(y=0, color='black', linewidth=0.5)
#
# plt.title('Modelo Estadistico de reversion a la media (BTC)')
# plt.legend()
# plt.show()
