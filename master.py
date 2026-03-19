import ccxt
import pandas as pd
import time
import os
from datetime import datetime

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'AVAX/USDT']
TIMEFRAME = '1m'  # Pedimos datos de 1 minuto para máxima precisión
LOOKBACK_MINUTES = 60 # Nuestra ventana de análisis (1 hora)
WINDOW = 30 
Z_THRESH = 2.5
LOG_FILE = 'real_time_forward_testing.csv'

exchange = ccxt.binance()

def fetch_real_time_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=300)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        
        df['mean_60m'] = df['close'].rolling(window=LOOKBACK_MINUTES).mean()
        df['std_60m'] = df['close'].rolling(window=LOOKBACK_MINUTES).std()
        
        df['z_score_now'] = (df['close'] - df['mean_60m']) / df['std_60m']
        
        df['vol_avg_hour'] = df['vol'].rolling(window=LOOKBACK_MINUTES).mean()
        
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        last_tick = df.iloc[-1]
        
        is_bullish = last_tick['close'] > last_tick['ema_200']
        has_momentum = last_tick['z_score_now'] > Z_THRESH
        high_volume = last_tick['vol'] > (last_tick['vol_avg_hour'] * 1.5) # Spike de volumen

        if is_bullish and has_momentum and high_volume:
            return "BUY SIGNAL 🚀", last_tick
        return "SCANNING 📡", last_tick

    except Exception as e:
        print(f"⚠️ Error en {symbol}: {e}")
        return None, None

print(f"⚡ Sistema de Baja Latencia Iniciado: {datetime.now()}")

# Para evitar que el log se llene de la misma señal cada minuto:
active_signals = {symbol: False for symbol in SYMBOLS}

while True:
    now = datetime.now()
    
    for symbol in SYMBOLS:
        status, data = fetch_real_time_analysis(symbol)
        
        if status == "BUY SIGNAL 🚀":
            if not active_signals[symbol]: # Solo avisar la primera vez que cruza el umbral
                print(f"🔥 {now.strftime('%H:%M:%S')} | {symbol} DETECTADO! | Price: {data['close']} | Z: {data['z_score_now']:.2f}")
                
                # Logging (Paso A)
                log_entry = pd.DataFrame([{
                    'timestamp': now, 'symbol': symbol, 'price': data['close'], 'z_score': data['z_score_now'], 'type': 'MOMENTUM_ENTRY'
                }])
                log_entry.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)
                
                active_signals[symbol] = True # Bloquear alertas repetidas hasta que se enfríe
        else:
            # Si el Z-Score baja de 1.0, "enfriamos" la señal para poder detectar la siguiente
            if data is not None and data['z_score_now'] < 1.0:
                active_signals[symbol] = False

    # Revisar cada 15 segundos para ser ultra-veloz
    time.sleep(15)
