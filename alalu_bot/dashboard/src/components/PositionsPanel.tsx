import type { ActiveTrade, HistoryEntry, MarketSnapshot } from '../types'

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

function ResultBadge({ type }: { type: string }) {
  if (type.includes('WIN'))
    return <span className="text-[11px] font-bold text-brand-green">WIN</span>
  if (type.includes('LIQ'))
    return (
      <span className="text-[11px] font-bold bg-brand-red/10 text-brand-red px-1.5 py-0.5 rounded-sm">
        LIQ
      </span>
    )
  return <span className="text-[11px] font-medium text-brand-red">LOSS</span>
}

interface Props {
  activeTrades: Record<string, ActiveTrade>
  history: HistoryEntry[]
  market: MarketSnapshot
}

export default function PositionsPanel({ activeTrades, history, market }: Props) {
  const positions = Object.entries(activeTrades)
  const recentHistory = [...history].reverse().slice(0, 10)

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
                    <span
                      className={`font-num font-bold text-base ${
                        isPos ? 'text-brand-green' : 'text-brand-red'
                      }`}
                    >
                      {pnl5x >= 0 ? '+' : ''}
                      {pnl5x.toFixed(2)}%
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <p className="text-tx-muted mb-0.5">Entrada</p>
                      <p className="font-num text-tx-primary">
                        ${trade.entry_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div>
                      <p className="text-tx-muted mb-0.5">Actual</p>
                      <p className="font-num text-tx-primary">
                        ${curr.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div>
                      <p className="text-tx-muted mb-0.5">Stop Loss</p>
                      <p className="font-num text-brand-red">
                        ${trade.sl_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                  </div>

                  {/* PnL bar */}
                  <div className="mt-3 h-0.5 bg-line rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isPos ? 'bg-brand-green' : 'bg-brand-red'
                      }`}
                      style={{ width: `${Math.min(Math.abs(pnl) * 10, 100)}%` }}
                    />
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Trade History */}
      <div className="bg-bg-card rounded-lg overflow-hidden flex-1">
        <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
          <h2 className="text-sm font-semibold text-tx-primary">Historial de Trades</h2>
          <span className="text-tx-muted text-xs">{history.length} total</span>
        </div>

        <div className="overflow-y-auto max-h-80">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-card">
              <tr className="border-b border-line">
                {['Hora', 'Par', 'Dir', 'PnL 5x', 'Min', 'Razón', ''].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-tx-muted font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentHistory.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-tx-muted">
                    Esperando primera señal...
                  </td>
                </tr>
              ) : (
                recentHistory.map((entry, i) => (
                  <tr
                    key={i}
                    className="border-b border-line/30 hover:bg-bg-hover transition-colors duration-100"
                  >
                    <td className="px-4 py-2.5 font-num text-tx-muted">{entry.time}</td>
                    <td className="px-4 py-2.5 font-medium text-tx-primary">
                      {entry.symbol.replace('/USDT', '')}
                    </td>
                    <td className="px-4 py-2.5">
                      <DirectionBadge direction={entry.direction} />
                    </td>
                    <td
                      className={`px-4 py-2.5 font-num font-semibold ${
                        entry.pnl_5x >= 0 ? 'text-brand-green' : 'text-brand-red'
                      }`}
                    >
                      {entry.pnl_5x >= 0 ? '+' : ''}${entry.pnl_5x.toFixed(2)}
                    </td>
                    <td className="px-4 py-2.5 font-num text-tx-muted">{entry.duration_min}m</td>
                    <td className="px-4 py-2.5 text-tx-muted capitalize">
                      {entry.exit_reason.replace(/_/g, ' ')}
                    </td>
                    <td className="px-4 py-2.5">
                      <ResultBadge type={entry.type} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
