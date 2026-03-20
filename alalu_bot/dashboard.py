import streamlit as st
import pandas as pd
import json
import time

st.set_page_config(page_title="Alalu Bot — Momentum Quant", layout="wide")
st.title("📊 Alalu Bot — Momentum Quant ($400)")

CAPITAL_TOTAL = 400.0
main_placeholder = st.empty()

while True:
    try:
        with open('market_state.json', 'r') as f:
            market_data = json.load(f)
        with open('portfolio.json', 'r') as f:
            port = json.load(f)

        with main_placeholder.container():
            if port.get('circuit_breaker'):
                st.error("🚨 CIRCUIT BREAKER ACTIVO — Motor detenido. Balance 5x cayó por debajo del 80%.")

            # --- MÉTRICAS PRINCIPALES ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Capital Inicial", f"${CAPITAL_TOTAL:.2f}")
            c2.metric(
                "Balance 1x (Spot)",
                f"${port['balance_1x']:.2f}",
                f"{((port['balance_1x'] - CAPITAL_TOTAL) / CAPITAL_TOTAL) * 100:.2f}%",
            )
            c3.metric(
                "Balance 5x (Futures)",
                f"${port['balance_5x']:.2f}",
                f"{((port['balance_5x'] - CAPITAL_TOTAL) / CAPITAL_TOTAL) * 100:.2f}%",
            )
            total_trades = len(port['history'])
            wins = sum(1 for t in port['history'] if t['type'] == 'WIN ✅')
            winrate = (wins / total_trades * 100) if total_trades > 0 else 0
            c4.metric("Win Rate (5x)", f"{winrate:.1f}%", f"{total_trades} trades")

            st.divider()

            # --- TABLA DE INDICADORES ---
            st.subheader("📡 Indicadores en Tiempo Real")
            rows = []
            for symbol, data in market_data.items():
                signal = data.get('signal')
                signal_label = "🟢 LONG" if signal == 'long' else ("🔴 SHORT" if signal == 'short' else "⚪ —")
                adx_val = data.get('adx')
                adx_str = f"{adx_val:.1f}" if adx_val is not None else "—"
                adx_flag = " ✓" if adx_val and adx_val > 25 else ""
                rows.append({
                    'Symbol': symbol,
                    'Precio': f"${data['price']:,.2f}" if data.get('price') else '—',
                    'ROC %': f"{data['roc']:+.2f}%" if data.get('roc') is not None else '—',
                    'RSI': f"{data['rsi']:.1f}" if data.get('rsi') is not None else '—',
                    'ADX': f"{adx_str}{adx_flag}",
                    '+DI': f"{data['plus_di']:.1f}" if data.get('plus_di') is not None else '—',
                    '-DI': f"{data['minus_di']:.1f}" if data.get('minus_di') is not None else '—',
                    'ATR %': f"{data['atr_pct']:.3f}%" if data.get('atr_pct') is not None else '—',
                    'Señal': signal_label,
                })
            st.dataframe(pd.DataFrame(rows).set_index('Symbol'), use_container_width=True)

            st.divider()

            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.subheader("📌 Posiciones Activas")
                if port['active_trades']:
                    for sym, trade in port['active_trades'].items():
                        curr_p = market_data.get(sym, {}).get('price', trade['entry_price'])
                        direction = trade['direction']
                        pnl = (
                            (curr_p - trade['entry_price']) / trade['entry_price'] * 100
                            if direction == 'long'
                            else (trade['entry_price'] - curr_p) / trade['entry_price'] * 100
                        )
                        pnl_5x = pnl * 5
                        label = "🟢 LONG" if direction == 'long' else "🔴 SHORT"
                        st.info(
                            f"**{sym}** {label} | "
                            f"Entrada: ${trade['entry_price']:,.4f} | "
                            f"PnL: {pnl:+.2f}% ({pnl_5x:+.2f}% 5x) | "
                            f"SL: ${trade['sl_price']:,.4f}"
                        )
                else:
                    st.write("Sin posiciones activas.")

            with col_right:
                st.subheader("📜 Historial de Operaciones")
                if port['history']:
                    cols = ['time', 'symbol', 'direction', 'pnl_5x', 'duration_min', 'exit_reason', 'type']
                    df_hist = pd.DataFrame(port['history'])[cols].tail(10)
                    df_hist.columns = ['Hora', 'Symbol', 'Dir', 'PnL 5x $', 'Duración min', 'Razón', 'Resultado']
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
                else:
                    st.write("Esperando primera señal...")

    except FileNotFoundError:
        st.info("⏳ Sincronizando con el motor de trading...")
    except Exception as e:
        st.error(f"Error: {e}")

    time.sleep(5)
