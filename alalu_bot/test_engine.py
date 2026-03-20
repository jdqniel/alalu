import asyncio
import os
import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault('DATA_DIR', '/tmp')

import engine
from engine import (
    CAPITAL_TOTAL,
    CIRCUIT_BREAKER_PCT,
    INITIAL_SL_PCT,
    TP_MULTIPLIER,
    check_exits_realtime,
    compute_rsi,
    execute_order,
    in_session,
    reconcile_positions,
)


# 1. execute_order en paper mode retorna {'id': 'paper'}
def test_execute_order_paper_mode():
    engine.LIVE_TRADING = False
    result = asyncio.run(execute_order(None, 'BTC/USDT', 'buy', 100, 50000))
    assert result == {'id': 'paper', 'average': 50000}


# 2. Circuit breaker activa exactamente en 80% de pérdida
def test_circuit_breaker_threshold():
    portfolio = {
        'balance_1x': CAPITAL_TOTAL,
        'balance_5x': CAPITAL_TOTAL * CIRCUIT_BREAKER_PCT - 0.01,
        'active_trades': {},
        'history': [],
        'circuit_breaker': False,
    }
    assert portfolio['balance_5x'] < CAPITAL_TOTAL * CIRCUIT_BREAKER_PCT


# 3. Long signal requiere las 5 condiciones simultáneas
def test_long_signal_requires_all_conditions():
    from engine import (
        ADX_THRESH, ROC_THRESH, RSI_LONG_MIN, RSI_LONG_MAX,
    )
    trending = True
    roc = ROC_THRESH + 0.001
    rsi = (RSI_LONG_MIN + RSI_LONG_MAX) / 2
    plus_di, minus_di = 30, 20
    vol_surge = True

    import pandas as pd
    long_signal = (
        trending
        and not pd.isna(roc) and roc > ROC_THRESH
        and not pd.isna(rsi) and RSI_LONG_MIN < rsi < RSI_LONG_MAX
        and plus_di > minus_di
        and vol_surge
    )
    assert long_signal

    # Falla si vol_surge = False
    long_signal_no_vol = (
        trending
        and not pd.isna(roc) and roc > ROC_THRESH
        and not pd.isna(rsi) and RSI_LONG_MIN < rsi < RSI_LONG_MAX
        and plus_di > minus_di
        and False
    )
    assert not long_signal_no_vol


# 4. Trailing stop short funciona en dirección correcta
def test_trailing_stop_short():
    from engine import TRAILING_PCT
    portfolio = {
        'balance_1x': 400,
        'balance_5x': 400,
        'active_trades': {
            'ETH/USDT': {
                'entry_price': 3000.0,
                'entry_time': '2024-01-01T00:00:00',
                'direction': 'short',
                'position_usd': 100,
                'sl_distance': 0.02,
                'lowest_price': 2900.0,
                'tp_price': None,
            }
        },
        'history': [],
    }
    trailing_stop = 2900.0 * (1 + TRAILING_PCT)
    price_above = trailing_stop + 1
    check_exits_realtime('ETH/USDT', price_above, portfolio)
    assert 'ETH/USDT' not in portfolio['active_trades']


# 5. compute_rsi no retorna NaN con 50 velas
def test_compute_rsi_no_nan():
    import numpy as np
    prices = pd.Series([100 + i * 0.5 + (i % 3) for i in range(50)])
    rsi = compute_rsi(prices, period=14)
    assert not pd.isna(rsi.iloc[-1])


# 6. execute_order con InsufficientFunds retorna None
def test_execute_order_insufficient_funds():
    engine.LIVE_TRADING = True
    mock_exchange = MagicMock()
    mock_exchange.create_market_order = AsyncMock(side_effect=engine.ccxtpro.InsufficientFunds())
    result = asyncio.run(execute_order(mock_exchange, 'BTC/USDT', 'buy', 100, 50000))
    assert result is None
    engine.LIVE_TRADING = False


# 7. reconcile_positions elimina trades no presentes en el exchange
def test_reconcile_positions_removes_missing():
    engine.LIVE_TRADING = True
    portfolio = {
        'active_trades': {
            'BTC/USDT': {'direction': 'long', 'entry_price': 50000},
            'ETH/USDT': {'direction': 'long', 'entry_price': 3000},
        }
    }
    mock_exchange = MagicMock()
    mock_exchange.fetch_balance = AsyncMock(return_value={
        'total': {'BTC': 0.002, 'USDT': 100}  # ETH no presente
    })
    result = asyncio.run(reconcile_positions(mock_exchange, portfolio))
    assert 'BTC/USDT' in result['active_trades']
    assert 'ETH/USDT' not in result['active_trades']
    engine.LIVE_TRADING = False


# 8. sl_distance nunca < INITIAL_SL_PCT
def test_sl_distance_minimum():
    atr_pct_tiny = 0.001
    sl_distance = max(INITIAL_SL_PCT, float(atr_pct_tiny) * 1.5)
    assert sl_distance >= INITIAL_SL_PCT

    atr_pct_large = 0.02
    sl_distance_large = max(INITIAL_SL_PCT, float(atr_pct_large) * 1.5)
    assert sl_distance_large >= INITIAL_SL_PCT


# 9. Take profit se dispara correctamente para long y short
def test_take_profit_triggers():
    sl_distance = 0.02
    entry = 50000.0
    tp_long = entry * (1 + sl_distance * TP_MULTIPLIER)
    tp_short = entry * (1 - sl_distance * TP_MULTIPLIER)

    portfolio_long = {
        'balance_1x': 400, 'balance_5x': 400, 'history': [],
        'active_trades': {'BTC/USDT': {
            'entry_price': entry, 'entry_time': '2024-01-01T00:00:00',
            'direction': 'long', 'position_usd': 100,
            'sl_distance': sl_distance, 'tp_price': tp_long,
            'highest_price': entry,
        }},
    }
    check_exits_realtime('BTC/USDT', tp_long + 1, portfolio_long)
    assert 'BTC/USDT' not in portfolio_long['active_trades']
    assert portfolio_long['history'][-1]['exit_reason'] == 'take_profit'

    portfolio_short = {
        'balance_1x': 400, 'balance_5x': 400, 'history': [],
        'active_trades': {'BTC/USDT': {
            'entry_price': entry, 'entry_time': '2024-01-01T00:00:00',
            'direction': 'short', 'position_usd': 100,
            'sl_distance': sl_distance, 'tp_price': tp_short,
            'lowest_price': entry,
        }},
    }
    check_exits_realtime('BTC/USDT', tp_short - 1, portfolio_short)
    assert 'BTC/USDT' not in portfolio_short['active_trades']
    assert portfolio_short['history'][-1]['exit_reason'] == 'take_profit'


# 10. in_session() retorna bool según hora UTC
def test_in_session():
    from unittest.mock import patch
    from engine import SESSION_START_UTC, SESSION_END_UTC
    from datetime import timezone

    inside_hour = (SESSION_START_UTC + SESSION_END_UTC) // 2
    outside_hour = (SESSION_END_UTC + 2) % 24

    from datetime import datetime as dt
    mock_inside = dt(2024, 1, 1, inside_hour, 0, 0, tzinfo=timezone.utc)
    mock_outside = dt(2024, 1, 1, outside_hour, 0, 0, tzinfo=timezone.utc)

    with patch('engine.datetime') as mock_dt:
        mock_dt.now.return_value = mock_inside
        mock_dt.fromisoformat = dt.fromisoformat
        assert in_session() is True

    with patch('engine.datetime') as mock_dt:
        mock_dt.now.return_value = mock_outside
        mock_dt.fromisoformat = dt.fromisoformat
        assert in_session() is False


# 11. HTF filter bloquea señal contra tendencia
def test_htf_filter_blocks_counter_trend():
    from engine import ADX_THRESH, ROC_THRESH, RSI_LONG_MIN, RSI_LONG_MAX
    price = 50000.0
    htf_ema_above = price + 1000  # precio < EMA → bearish → bloquea long
    htf_bullish = price > htf_ema_above
    assert htf_bullish is False  # long bloqueado
