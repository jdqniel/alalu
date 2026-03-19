import ccxt
import pandas as pd
import time
import os
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURACIÓN PRO (LEVERAGE 5X)
# ==========================================
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
TIMEFRAME = '1m'
WINDOW = 30
Z_THRESH = 2.5
LEVERAGE = 5  # <--- Tu multiplicador de riesgo
TP_PCT = 0.03 # Ganancia en precio (3% real = 15% con 5x)
SL_PCT = 0.015 # Pérdida en precio (1.5% real = 7.5% con 5x)
LOG_FILE = 'leverage_forward_testing.csv'

exchange = ccxt.binance()

# Diccionario para rastrear posiciones abiertas simuladas
# Formato: {'BTC/USDT': {'entry_price': 70000, 'status': 'LONG'}}
active_positions = {symbol: None for symbol in SYMBOLS}

def fetch_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        
        # Indicadores de Ventana Deslizante
        df['mean'] = df['close'].rolling(window=WINDOW).mean()
        df['std'] = df['close'].rolling(window=WINDOW).std()
        df['z_score'] = (df['close'] - df['mean']) / df['std']
        df['vol_avg'] = df['vol'].rolling(window=WINDOW).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        return df.iloc[-1]
    except Exception as e:
        print(f"Error en {symbol}: {e}")
        return None

def log_trade(data):
    """Guarda la operación en el CSV con las nuevas métricas de BI."""
    df_log = pd.DataFrame([data])
    df_log.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)

# ==========================================
# 🚀 BUCLE DE ALTA FRECUENCIA CON GESTIÓN
# ==========================================
print(f"🔥 Radar de Momentum 5x Leverage Iniciado...")

while True:
    for symbol in SYMBOLS:
        last_tick = fetch_analysis(symbol)
        if last_tick is None: continue

        current_price = last_tick['close']
        pos = active_positions[symbol]

        # 1. SI NO TENEMOS POSICIÓN: Buscar Entrada
        if pos is None:
            if (current_price > last_tick['ema_200'] and 
                last_tick['z_score'] > Z_THRESH and 
                last_tick['vol'] > (last_tick['vol_avg'] * 1.5)):
                
                # Cálculo de Riesgo (BI Risk Assessment)
                liq_price = current_price * (1 - (1/LEVERAGE)) # Precio de liquidación aproximado
                
                active_positions[symbol] = {
                    'entry_price': current_price,
                    'timestamp': datetime.now()
                }
                
                print(f"🚀 ENTRADA {symbol} a {current_price} | Peligro (Liq): {liq_price:.2f}")
                
                log_trade({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'type': 'ENTRY',
                    'price': current_price,
                    'liq_price': round(liq_price, 2),
                    'leverage': LEVERAGE,
                    'pnl_leveraged': 0
                })

        # 2. SI YA ESTAMOS DENTRO: Buscar Salida (TP/SL)
        else:
            entry = pos['entry_price']
            price_change = (current_price - entry) / entry
            
            # Verificamos si tocó TP o SL
            if price_change >= TP_PCT or price_change <= -SL_PCT:
                # El P&L se multiplica por el apalancamiento
                final_pnl = price_change * LEVERAGE * 100
                status = "EXIT ✅ (WIN)" if final_pnl > 0 else "EXIT ❌ (LOSS)"
                
                print(f"{status} {symbol} | Price: {current_price} | Net P&L (5x): {final_pnl:.2f}%")
                
                log_trade({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'type': 'EXIT',
                    'price': current_price,
                    'liq_price': 0,
                    'leverage': LEVERAGE,
                    'pnl_leveraged': round(final_pnl, 2)
                })
                
                active_positions[symbol] = None # Cerramos posición

    time.sleep(15) # Escaneo cada 15 segundos
