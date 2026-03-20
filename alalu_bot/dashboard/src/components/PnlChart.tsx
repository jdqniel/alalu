import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import type { TradeEntry } from '../types'

interface Props {
  trades: TradeEntry[]
}

interface BarData {
  idx: number
  pnl: number
  symbol: string
  direction: string
  reason: string
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: { payload: BarData }[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const isPos = d.pnl >= 0
  return (
    <div className="bg-bg-elevated border border-line rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-tx-muted mb-1">
        #{d.idx} · {d.symbol} · {d.direction.toUpperCase()}
      </p>
      <p className={`font-num font-semibold ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
        {isPos ? '+' : ''}${d.pnl.toFixed(2)}
      </p>
      <p className="text-tx-muted mt-0.5">{d.reason.replace(/_/g, ' ')}</p>
    </div>
  )
}

export default function PnlChart({ trades }: Props) {
  const data: BarData[] = trades.map((t, i) => ({
    idx: i + 1,
    pnl: parseFloat(t.pnl_usd),
    symbol: t.symbol.replace('/USDT', ''),
    direction: t.direction,
    reason: t.exit_reason,
  }))

  return (
    <div className="bg-bg-card rounded-lg overflow-hidden">
      <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
        <h2 className="text-sm font-semibold text-tx-primary">PnL por Trade</h2>
        <span className="text-tx-muted text-xs">{trades.length} trades</span>
      </div>
      <div className="p-4">
        {trades.length === 0 ? (
          <div className="h-28 flex items-center justify-center">
            <p className="text-tx-muted text-sm">Sin trades registrados</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={110}>
            <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }} barCategoryGap="20%">
              <XAxis dataKey="idx" hide />
              <YAxis
                tick={{ fill: '#5E6673', fontSize: 10 }}
                width={44}
                tickFormatter={(v) => `$${v.toFixed(0)}`}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#1E2329' }} />
              <ReferenceLine y={0} stroke="#2B3139" />
              <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? '#0ECB81' : '#F6465D'} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
