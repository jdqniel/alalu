import ccxt
import pandas as pd
import pickle
import time
import os
from datetime import datetime

# --- CONFIGURACIÓN DE REALIDAD ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
CAPITAL_TOTAL = 400.0
RIESGO_POR_TRADE = 100.0 
Z_THRESH = 2.5
TP_PCT = 0.03   
SL_PCT = 0.015  
BINANCE_FEE = 0.001 # 0.1% por operación (Estándar de Binance)

STATE_FILE = 'market_state.pkl'
PORTFOLIO_FILE = 'portfolio.pkl'

exchange = ccxt.binance()

def run_motor():
    if not os.path.exists(PORTFOLIO_FILE):
        portfolio = {
            'balance_1x': CAPITAL_TOTAL,
            'balance_5x': CAPITAL_TOTAL,
            'active_trades': {}, 
            'history': []
        }
    else:
        with open(PORTFOLIO_FILE, 'rb') as f:
            portfolio = pickle.load(f)

    print(f"💰 Simulación REAL iniciada (Con Fees del 0.1%).")

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

                # --- GESTIÓN DE TRADES ---
                if symbol in portfolio['active_trades']:
                    trade = portfolio['active_trades'][symbol]
                    pnl_pct = (current_price - trade['entry_price']) / trade['entry_price']
                    
                    # Verificamos salida o LIQUIDACIÓN en 5x
                    # Si el precio cae 20%, en 5x pierdes el 100% (Liquidación)
                    if pnl_pct <= -0.20:
                        is_liquidated = True
                    else:
                        is_liquidated = False

                    if pnl_pct >= TP_PCT or pnl_pct <= -SL_PCT or is_liquidated:
                        # Cálculo con FEES (Entrada + Salida)
                        fee_total_1x = RIESGO_POR_TRADE * BINANCE_FEE * 2
                        fee_total_5x = (RIESGO_POR_TRADE * 5) * (BINANCE_FEE/2) * 2 # Fees de futuros son menores

                        if is_liquidated:
                            gain_1x = RIESGO_POR_TRADE * pnl_pct - fee_total_1x
                            gain_5x = -RIESGO_POR_TRADE # Pérdida total
                        else:
                            gain_1x = (RIESGO_POR_TRADE * pnl_pct) - fee_total_1x
                            gain_5x = (RIESGO_POR_TRADE * pnl_pct * 5) - fee_total_5x
                        
                        portfolio['balance_1x'] += gain_1x
                        portfolio['balance_5x'] += gain_5x
                        
                        portfolio['history'].append({
                            'time': now.strftime("%H:%M"),
                            'symbol': symbol,
                            'pnl_5x': round(gain_5x, 2),
                            'type': 'LIQ 💀' if is_liquidated else ('WIN ✅' if gain_5x > 0 else 'LOSS ❌')
                        })
                        del portfolio['active_trades'][symbol]

                # --- ENTRADA ---
                elif z_score > Z_THRESH and df['vol'].iloc[-1] > df['vol_avg'].iloc[-1]:
                    if portfolio['balance_5x'] >= RIESGO_POR_TRADE:
                        portfolio['active_trades'][symbol] = {'entry_price': current_price}

            except Exception as e:
                print(f"Error: {e}")

        with open(STATE_FILE, 'wb') as f: pickle.dump(market_snapshot, f)
        with open(PORTFOLIO_FILE, 'wb') as f: pickle.dump(portfolio, f)
        time.sleep(15)

if __name__ == "__main__":
    run_motor()
