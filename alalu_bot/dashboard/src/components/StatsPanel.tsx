import type { TradeEntry } from '../types'

function StatItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-tx-muted uppercase tracking-wider">{label}</span>
      <span className={`font-num text-base font-semibold ${color ?? 'text-tx-primary'}`}>{value}</span>
    </div>
  )
}

interface Props {
  trades: TradeEntry[]
  capital: number
}

export default function StatsPanel({ trades, capital }: Props) {
  if (trades.length === 0) {
    return (
      <div className="bg-bg-card rounded-lg h-full flex items-center justify-center">
        <p className="text-tx-muted text-sm">Sin trades registrados</p>
      </div>
    )
  }

  const pnls = trades.map((t) => parseFloat(t.pnl_usd))
  const wins = pnls.filter((p) => p > 0)
  const losses = pnls.filter((p) => p < 0)
  const totalPnl = pnls.reduce((a, b) => a + b, 0)
  const grossWin = wins.reduce((a, b) => a + b, 0)
  const grossLoss = Math.abs(losses.reduce((a, b) => a + b, 0))
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : wins.length > 0 ? Infinity : 0
  const avgWin = wins.length > 0 ? grossWin / wins.length : 0
  const avgLoss = losses.length > 0 ? grossLoss / losses.length : 0
  const best = Math.max(...pnls)
  const worst = Math.min(...pnls)
  const returnPct = (totalPnl / capital) * 100

  let maxStreak = 0
  let streak = 0
  for (const p of pnls) {
    if (p < 0) { streak++; maxStreak = Math.max(maxStreak, streak) }
    else streak = 0
  }

  const pfStr = profitFactor === Infinity ? '∞' : profitFactor.toFixed(2)
  const pnlColor = totalPnl >= 0 ? 'text-brand-green' : 'text-brand-red'
  const pfColor = profitFactor >= 1.5 ? 'text-brand-green' : profitFactor >= 1 ? 'text-brand-gold' : 'text-brand-red'

  return (
    <div className="bg-bg-card rounded-lg overflow-hidden h-full">
      <div className="px-5 py-3.5 border-b border-line">
        <h2 className="text-sm font-semibold text-tx-primary">Estadísticas</h2>
      </div>
      <div className="p-5 grid grid-cols-2 gap-x-8 gap-y-4">
        <StatItem label="PnL Total" value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`} color={pnlColor} />
        <StatItem label="Retorno" value={`${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%`} color={pnlColor} />
        <StatItem label="Profit Factor" value={pfStr} color={pfColor} />
        <StatItem label="Trades Totales" value={`${trades.length}`} />
        <StatItem label="Avg Ganancia" value={`+$${avgWin.toFixed(2)}`} color="text-brand-green" />
        <StatItem label="Avg Pérdida" value={`-$${avgLoss.toFixed(2)}`} color="text-brand-red" />
        <StatItem label="Mejor Trade" value={`+$${best.toFixed(2)}`} color="text-brand-green" />
        <StatItem label="Peor Trade" value={`$${worst.toFixed(2)}`} color="text-brand-red" />
        <StatItem
          label="Racha Pérd. Máx"
          value={`${maxStreak} seguidas`}
          color={maxStreak >= 4 ? 'text-brand-red' : maxStreak >= 2 ? 'text-brand-gold' : 'text-tx-primary'}
        />
        <StatItem label="Win Rate" value={`${trades.length > 0 ? ((wins.length / trades.length) * 100).toFixed(1) : 0}%`} />
      </div>
    </div>
  )
}
