import type { ActiveTrade, MarketSnapshot, TradeEntry } from '../types'

function DirectionBadge({ direction }: { direction: 'long' | 'short' }) {
  return (
    <span
      className={`text-[11px] font-bold px-2 py-0.5 rounded-sm ${
        direction === 'long'
          ? 'bg-brand-green/10 text-brand-green'
          : 'bg-brand-red/10 text-brand-red'
      }`}
    >
      {direction.toUpperCase()}
    </span>
  )
}

function ReasonBadge({ reason }: { reason: string }) {
  const map: Record<string, string> = {
    take_profit: '🎯',
    trailing_stop: '📈',
    stop_loss: '🛑',
    time_exit: '⏱',
    liquidation: '💀',
  }
  const emoji = map[reason] ?? ''
  return (
    <span className="text-tx-muted capitalize">
      {emoji} {reason.replace(/_/g, ' ')}
    </span>
  )
}

interface Props {
  activeTrades: Record<string, ActiveTrade>
  trades: TradeEntry[]
  market: MarketSnapshot
}

export default function PositionsPanel({ activeTrades, trades, market }: Props) {
  const positions = Object.entries(activeTrades)
  const recentTrades = [...trades].reverse().slice(0, 20)

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Active Positions */}
      <div className="bg-bg-card rounded-lg overflow-hidden">
        <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
          <h2 className="text-sm font-semibold text-tx-primary">Posiciones Activas</h2>
          <span className="text-tx-muted text-xs">
            {positions.length} abierta{positions.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="p-3 space-y-2 min-h-[120px]">
          {positions.length === 0 ? (
            <p className="text-tx-muted text-sm text-center py-6">Sin posiciones activas</p>
          ) : (
            positions.map(([symbol, trade]) => {
              const curr = market[symbol]?.price ?? trade.entry_price
              const pnl =
                trade.direction === 'long'
                  ? ((curr - trade.entry_price) / trade.entry_price) * 100
                  : ((trade.entry_price - curr) / trade.entry_price) * 100
              const pnl5x = pnl * 5
              const isPos = pnl >= 0

              return (
                <div key={symbol} className="bg-bg-elevated rounded-lg p-3.5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-tx-primary">
                        {symbol.replace('/USDT', '')}
                        <span className="text-tx-muted font-normal">/USDT</span>
                      </span>
                      <DirectionBadge direction={trade.direction} />
                    </div>
                    <div className="text-right">
                      <p className={`font-num font-bold text-base ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
                        {pnl5x >= 0 ? '+' : ''}{pnl5x.toFixed(2)}%
                      </p>
                      <p className={`font-num text-xs ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
                        {isPos ? '+' : ''}${((pnl5x / 100) * trade.position_usd).toFixed(2)}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <p className="text-tx-muted mb-0.5">Entrada</p>
                      <p className="font-num text-tx-primary">
                        ${trade.entry_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div>
                      <p className="text-tx-muted mb-0.5">Stop Loss</p>
                      <p className="font-num text-brand-red">
                        ${trade.sl_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div>
                      <p className="text-tx-muted mb-0.5">Take Profit</p>
                      <p className="font-num text-brand-green">
                        {trade.tp_price
                          ? `$${trade.tp_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                          : '—'}
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 h-0.5 bg-line rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${isPos ? 'bg-brand-green' : 'bg-brand-red'}`}
                      style={{ width: `${Math.min(Math.abs(pnl) * 10, 100)}%` }}
                    />
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Trade History — desde CSV persistente */}
      <div className="bg-bg-card rounded-lg overflow-hidden flex-1">
        <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
          <h2 className="text-sm font-semibold text-tx-primary">Historial de Trades</h2>
          <span className="text-tx-muted text-xs">{trades.length} total</span>
        </div>

        <div className="overflow-y-auto max-h-80">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-card">
              <tr className="border-b border-line">
                {['Hora', 'Par', 'Dir', 'PnL $', 'PnL %', 'Min', 'Razón'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-tx-muted font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentTrades.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-tx-muted">
                    Esperando primera señal...
                  </td>
                </tr>
              ) : (
                recentTrades.map((entry, i) => {
                  const pnl = parseFloat(entry.pnl_usd)
                  const pnlPct = parseFloat(entry.pnl_pct)
                  const isPos = pnl >= 0
                  const time = entry.timestamp.slice(11, 16)
                  return (
                    <tr key={i} className="border-b border-line/30 hover:bg-bg-hover transition-colors duration-100">
                      <td className="px-4 py-2.5 font-num text-tx-muted">{time}</td>
                      <td className="px-4 py-2.5 font-medium text-tx-primary">
                        {entry.symbol.replace('/USDT', '')}
                      </td>
                      <td className="px-4 py-2.5">
                        <DirectionBadge direction={entry.direction} />
                      </td>
                      <td className={`px-4 py-2.5 font-num font-semibold ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
                        {isPos ? '+' : ''}${pnl.toFixed(2)}
                      </td>
                      <td className={`px-4 py-2.5 font-num ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
                        {isPos ? '+' : ''}{pnlPct.toFixed(2)}%
                      </td>
                      <td className="px-4 py-2.5 font-num text-tx-muted">{entry.duration_min}m</td>
                      <td className="px-4 py-2.5">
                        <ReasonBadge reason={entry.exit_reason} />
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
