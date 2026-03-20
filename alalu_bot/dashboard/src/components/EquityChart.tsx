import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import type { TradeEntry } from '../types'

interface Props {
  trades: TradeEntry[]
  capital: number
}

interface Point {
  idx: number
  balance: number
  label: string
  pnl: number
}

function buildCurve(trades: TradeEntry[], capital: number): Point[] {
  let balance = capital
  const points: Point[] = [{ idx: 0, balance, label: 'Inicio', pnl: 0 }]
  for (let i = 0; i < trades.length; i++) {
    const pnl = parseFloat(trades[i].pnl_usd)
    balance = parseFloat((balance + pnl).toFixed(2))
    points.push({
      idx: i + 1,
      balance,
      label: trades[i].symbol.replace('/USDT', ''),
      pnl,
    })
  }
  return points
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  if (d.idx === 0) return null
  const isPos = d.pnl >= 0
  return (
    <div className="bg-bg-elevated border border-line rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-tx-muted mb-1">Trade #{d.idx} · {d.label}</p>
      <p className="font-num text-tx-primary font-semibold">Balance: ${d.balance.toFixed(2)}</p>
      <p className={`font-num font-medium ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
        PnL: {isPos ? '+' : ''}${d.pnl.toFixed(2)}
      </p>
    </div>
  )
}

export default function EquityChart({ trades, capital }: Props) {
  const data = buildCurve(trades, capital)
  const values = data.map((d) => d.balance)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const padding = (max - min) * 0.1 || 20
  const isUp = data[data.length - 1]?.balance >= capital

  return (
    <div className="bg-bg-card rounded-lg overflow-hidden">
      <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
        <h2 className="text-sm font-semibold text-tx-primary">Equity Curve</h2>
        <span className="text-tx-muted text-xs">{trades.length} trades</span>
      </div>
      <div className="p-4">
        {trades.length === 0 ? (
          <div className="h-40 flex items-center justify-center">
            <p className="text-tx-muted text-sm">Sin trades registrados</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={isUp ? '#0ECB81' : '#F6465D'} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={isUp ? '#0ECB81' : '#F6465D'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="idx" hide />
              <YAxis
                domain={[min - padding, max + padding]}
                tick={{ fill: '#5E6673', fontSize: 10 }}
                width={52}
                tickFormatter={(v) => `$${v.toFixed(0)}`}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={capital} stroke="#2B3139" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="balance"
                stroke={isUp ? '#0ECB81' : '#F6465D'}
                strokeWidth={2}
                fill="url(#equityGrad)"
                dot={false}
                activeDot={{ r: 4, fill: isUp ? '#0ECB81' : '#F6465D', strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
