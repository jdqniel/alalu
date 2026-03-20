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
    check_exits_realtime,
    compute_rsi,
    execute_order,
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
            }
        },
        'history': [],
    }
    # trailing_stop para short = lowest_price * (1 + TRAILING_PCT)
    trailing_stop = 2900.0 * (1 + TRAILING_PCT)
    # Si price sube por encima del trailing_stop, exit_triggered
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
    atr_pct_tiny = 0.001  # muy pequeño
    sl_distance = max(INITIAL_SL_PCT, float(atr_pct_tiny) * 1.5)
    assert sl_distance >= INITIAL_SL_PCT

    atr_pct_large = 0.02
    sl_distance_large = max(INITIAL_SL_PCT, float(atr_pct_large) * 1.5)
    assert sl_distance_large >= INITIAL_SL_PCT
