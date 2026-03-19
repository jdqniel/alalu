import streamlit as st
import pandas as pd
import pickle
import time
import plotly.graph_objects as go

st.set_page_config(page_title="Experimento Alalu $400", layout="wide")

st.title("🧪 Experimento: Momentum 1x vs 5x ($400)")

main_placeholder = st.empty()

while True:
    try:
        with open('market_state.pkl', 'rb') as f: market_data = pickle.load(f)
        with open('portfolio.pkl', 'rb') as f: port = pickle.load(f)

        with main_placeholder.container():
            # MÉTRICAS DE BI
            c1, c2, c3 = st.columns(3)
            c1.metric("Balance Inicial", "$400.00")
            c2.metric("Balance 1x (Spot)", f"${port['balance_1x']:.2f}", 
                      f"{((port['balance_1x']-400)/400)*100:.2f}%")
            c3.metric("Balance 5x (Futures)", f"${port['balance_5x']:.2f}", 
                      f"{((port['balance_5x']-400)/400)*100:.2f}%")

            st.divider()

            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.subheader("📡 Posiciones Activas")
                if port['active_trades']:
                    for sym, data in port['active_trades'].items():
                        curr_p = market_data[sym]['close'].iloc[-1]
                        pnl = (curr_p - data['entry_price']) / data['entry_price'] * 100
                        st.info(f"**{sym}** | Entrada: {data['entry_price']} | PnL Actual: {pnl:.2f}%")
                else:
                    st.write("Sin posiciones activas.")

            with col_right:
                st.subheader("📜 Historial de Operaciones")
                if port['history']:
                    st.table(pd.DataFrame(port['history']).tail(5))
                else:
                    st.write("Esperando primera señal...")

    except:
        st.info("Sincronizando con el motor de trading...")
    
    time.sleep(5)
