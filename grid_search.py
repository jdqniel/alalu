# Fase 2: Grid search sobre ventana de rolling y umbral de Z-Score (BTC/USDT 1h)
# Busca los parámetros óptimos para la estrategia de la Fase 1.
# Subimos a 1h para tener más historia y reducir ruido de microestructura.
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

exchange = ccxt.binance()
#
# short_window = 20
# long_window = 200
# fee = 0.001
#
bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h')
df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# df['ema_200'] = df['close'].ewm(span=long_window, adjust=False).mean()
# df['mean_20'] = df['close'].rolling(window=short_window).mean()
# df['std_20'] = df['close'].rolling(window=short_window).std()
# df['z_score'] = (df['close'] - df['mean_20']) / df['std_20']
#
# df['signal'] = np.where((df['close'] > df['ema_200']) & (df['z_score'] < -3), 'BUY', 
#                         np.where((df['close'] < df['ema_200']) & (df['z_score'] > 3), 'SELL', 'HOLD'))
# # print(df[['close', 'ema_200', 'z_score', 'signal']].tail())
#
# df['market_return'] = df['close'].pct_change()
#
# df['position'] = df['signal'].replace({'BUY': 1, 'SELL': -1, 'HOLD':0}).shift(1)
# df['position'] = pd.to_numeric(df['position'].fillna(0))
#
# df['strategy_return'] = df['position'] * df['market_return']
#
# df['cumulative_market'] = (1 + df['market_return']).cumprod()
# df['cumulative_strategy'] = (1 + df['strategy_return']).cumprod()
#
# df['trades'] = df['position'].diff().fillna(0).abs()
#
# df['strategy_net_return'] = df['strategy_return'] - (df['trades'] * fee)
#
# df['cumulative_strategy_net'] = (1 + df['strategy_net_return']).cumprod()
#
# print(f"Retorno Neto (Después de Comisiones): {(df['cumulative_strategy_net'].iloc[-1] - 1) * 100:.2f}%")
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

def backtest_strategy(df, window, z_thresh):
    # Copiamos el dataframe para no ensuciar el original
    temp_df = df.copy()
    
    # Indicadores
    temp_df['ema_200'] = temp_df['close'].ewm(span=200, adjust=False).mean()
    temp_df['mean'] = temp_df['close'].rolling(window=window).mean()
    temp_df['std'] = temp_df['close'].rolling(window=window).std()
    temp_df['z_score'] = (temp_df['close'] - temp_df['mean']) / temp_df['std']
    
    # Señales
    temp_df['signal'] = np.where((temp_df['close'] > temp_df['ema_200']) & (temp_df['z_score'] < -z_thresh), 'BUY', 
                        np.where((temp_df['close'] < temp_df['ema_200']) & (temp_df['z_score'] > z_thresh), 'SELL', 'HOLD'))
    
    # Retornos y Comisiones
    temp_df['market_return'] = temp_df['close'].pct_change()
    temp_df['position'] = temp_df['signal'].replace({'BUY': 1, 'SELL': -1, 'HOLD':0}).shift(1).fillna(0)
    temp_df['strategy_return'] = temp_df['position'] * temp_df['market_return']
    temp_df['trades'] = temp_df['position'].diff().fillna(0).abs()
    
    # Retorno Neto
    fee = 0.001
    net_return = temp_df['strategy_return'] - (temp_df['trades'] * fee)
    return (1 + net_return).cumprod().iloc[-1] - 1

# --- BUCLE DE OPTIMIZACIÓN ---
results = []
for w in [10, 20, 30, 50]: # Probamos diferentes ventanas
    for z in [1.5, 2.0, 2.5, 3.0]: # Probamos diferentes sensibilidades
        profit = backtest_strategy(df, w, z)
        results.append({'ventana': w, 'z_score': z, 'profit': profit * 100})

# Convertimos a DataFrame para ver el ranking
df_results = pd.DataFrame(results).sort_values(by='profit', ascending=False)
print(df_results)
