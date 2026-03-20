export interface MarketData {
  price: number
  roc: number | null
  rsi: number | null
  adx: number | null
  plus_di: number | null
  minus_di: number | null
  atr_pct: number | null
  htf_ema: number | null
  htf_trend: 'bull' | 'bear' | null
  signal: 'long' | 'short' | null
  regime: 'normal' | 'bull_run' | null
  timestamp: string
}

export interface ActiveTrade {
  entry_price: number
  entry_time: string
  direction: 'long' | 'short'
  position_usd: number
  sl_distance: number
  sl_price: number
  tp_price: number | null
  highest_price: number
  lowest_price: number
}

export interface TradeEntry {
  timestamp: string
  symbol: string
  direction: 'long' | 'short'
  entry_price: string
  exit_price: string
  pnl_usd: string
  pnl_pct: string
  duration_min: string
  exit_reason: string
  order_id: string
}

export interface HistoryEntry {
  time: string
  symbol: string
  direction: 'long' | 'short'
  pnl_5x: number
  duration_min: number
  exit_reason: string
  type: string
}

export interface Portfolio {
  balance_1x: number
  balance_5x: number
  active_trades: Record<string, ActiveTrade>
  history: HistoryEntry[]
  circuit_breaker: boolean
}

export type MarketSnapshot = Record<string, MarketData>
