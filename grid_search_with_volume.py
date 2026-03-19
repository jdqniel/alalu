# Fase 3: Grid search con volumen como confirmación + TP/SL explícitos (BTC/USDT 1h)
# Cambio conceptual: de reversión a la media → momentum (Z-Score positivo = fuerza).
# El volumen debe superar su media para que la señal sea válida.
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

def backtest_momentum_sl_tp(df, window, z_thresh, tp_pct=0.03, sl_pct=0.015):
    temp_df = df.copy()
    
    # 1. Indicadores (Añadimos volumen para BI)
    temp_df['ema_200'] = temp_df['close'].ewm(span=200, adjust=False).mean()
    temp_df['mean_p'] = temp_df['close'].rolling(window=window).mean()
    temp_df['std_p'] = temp_df['close'].rolling(window=window).std()
    temp_df['z_score'] = (temp_df['close'] - temp_df['mean_p']) / temp_df['std_p']
    temp_df['vol_mean'] = temp_df['volume'].rolling(window=window).mean()

    # 2. Lógica de Simulación
    in_position = 0
    entry_price = 0
    total_return = 1.0
    fee = 0.001
    
    for i in range(len(temp_df)):
        row = temp_df.iloc[i]
        
        if in_position != 0:
            price_change = (row['close'] - entry_price) / entry_price
            current_pnl = price_change if in_position == 1 else -price_change
            
            if current_pnl >= tp_pct or current_pnl <= -sl_pct:
                total_return *= (1 + current_pnl - (fee * 2))
                in_position = 0 
        else:
            # CAMBIO CLAVE: Compramos cuando el Z-Score es POSITIVO (Fuerza)
            # Y el volumen confirma el movimiento
            if row['close'] > row['ema_200'] and row['z_score'] > z_thresh and row['volume'] > row['vol_mean']:
                in_position = 1
                entry_price = row['close']
                
    return total_return - 1
# --- Optimización con SL/TP ---
results = []
for w in [10, 20, 30]:
    for z in [2.0, 2.5, 3.0]:
        profit = backtest_momentum_sl_tp(df, w, z, tp_pct=0.02, sl_pct=0.01)
        results.append({'ventana': w, 'z_score': z, 'profit': profit * 100})

print(pd.DataFrame(results).sort_values(by='profit', ascending=False))
