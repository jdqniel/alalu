import ccxt
import pandas as pd
import pickle
import time
import os
from datetime import datetime

# --- CONFIGURACIÓN DEL EXPERIMENTO ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
CAPITAL_TOTAL = 400.0
RIESGO_POR_TRADE = 100.0  # Cada señal usa $100
Z_THRESH = 2.5
TP_PCT = 0.03   # +3%
SL_PCT = 0.015  # -1.5%

exchange = ccxt.binance()

# Archivos de estado
STATE_FILE = 'market_state.pkl'
PORTFOLIO_FILE = 'portfolio.pkl'

def run_motor():
    # Inicializar portafolio si no existe
    if not os.path.exists(PORTFOLIO_FILE):
        portfolio = {
            'balance_1x': CAPITAL_TOTAL,
            'balance_5x': CAPITAL_TOTAL,
            'active_trades': {}, # {symbol: {entry_price, amount_usd, timestamp}}
            'history': []
        }
    else:
        with open(PORTFOLIO_FILE, 'rb') as f:
            portfolio = pickle.load(f)

    print(f"💰 Experimento $400 Iniciado. 1x: ${portfolio['balance_1x']} | 5x: ${portfolio['balance_5x']}")

    while True:
        market_snapshot = {}
        now = datetime.now()

        for symbol in SYMBOLS:
            try:
                bars = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=100)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                
                # Indicadores
                df['mean'] = df['close'].rolling(30).mean()
                df['std'] = df['close'].rolling(30).std()
                df['z_score'] = (df['close'] - df['mean']) / df['std']
                df['vol_avg'] = df['vol'].rolling(30).mean()
                
                current_price = df['close'].iloc[-1]
                z_score = df['z_score'].iloc[-1]
                market_snapshot[symbol] = df

                # --- LÓGICA DE TRADING VIRTUAL ---
                # 1. ¿Cerrar trade activo?
                if symbol in portfolio['active_trades']:
                    trade = portfolio['active_trades'][symbol]
                    pnl_pct = (current_price - trade['entry_price']) / trade['entry_price']
                    
                    if pnl_pct >= TP_PCT or pnl_pct <= -SL_PCT:
                        # Calcular resultados
                        gain_1x = RIESGO_POR_TRADE * pnl_pct
                        gain_5x = RIESGO_POR_TRADE * pnl_pct * 5
                        
                        portfolio['balance_1x'] += gain_1x
                        portfolio['balance_5x'] += gain_5x
                        
                        portfolio['history'].append({
                            'time': now.strftime("%H:%M"),
                            'symbol': symbol,
                            'pnl_1x': round(gain_1x, 2),
                            'pnl_5x': round(gain_5x, 2),
                            'type': 'WIN' if pnl_pct > 0 else 'LOSS'
                        })
                        del portfolio['active_trades'][symbol]
                        print(f"✅ VENTA {symbol} | PnL 5x: {gain_5x:.2f}")

                # 2. ¿Abrir nuevo trade?
                elif z_score > Z_THRESH and df['vol'].iloc[-1] > df['vol_avg'].iloc[-1]:
                    if portfolio['balance_5x'] >= RIESGO_POR_TRADE: # Check de capital
                        portfolio['active_trades'][symbol] = {
                            'entry_price': current_price,
                            'time': now.strftime("%H:%M")
                        }
                        print(f"🚀 COMPRA {symbol} detectada a {current_price}")

            except Exception as e:
                print(f"Error: {e}")

        # Guardar estados
        with open(STATE_FILE, 'wb') as f: pickle.dump(market_snapshot, f)
        with open(PORTFOLIO_FILE, 'wb') as f: pickle.dump(portfolio, f)
        
        time.sleep(15)

if __name__ == "__main__":
    run_motor()
