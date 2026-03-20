import type { MarketSnapshot } from '../types'

function fmt(val: number | null, dec = 1): string {
  return val === null || val === undefined ? '—' : val.toFixed(dec)
}

function SignalBadge({ signal }: { signal: 'long' | 'short' | null }) {
  if (!signal) return <span className="text-tx-muted">—</span>
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-sm ${
        signal === 'long'
          ? 'bg-brand-green/10 text-brand-green'
          : 'bg-brand-red/10 text-brand-red'
      }`}
    >
      <span className={`w-1 h-1 rounded-full ${signal === 'long' ? 'bg-brand-green' : 'bg-brand-red'}`} />
      {signal.toUpperCase()}
    </span>
  )
}

function RsiBar({ rsi }: { rsi: number | null }) {
  if (rsi === null) return <span className="text-tx-muted font-num">—</span>
  const color =
    rsi > 70 ? 'text-brand-red' : rsi < 30 ? 'text-brand-red' : rsi > 50 ? 'text-brand-green' : 'text-tx-secondary'
  return <span className={`font-num ${color}`}>{rsi.toFixed(1)}</span>
}

function HtfBadge({ trend }: { trend: 'bull' | 'bear' | null }) {
  if (!trend) return <span className="text-tx-muted">—</span>
  return (
    <span className={`font-bold text-sm ${trend === 'bull' ? 'text-brand-green' : 'text-brand-red'}`}>
      {trend === 'bull' ? '▲' : '▼'}
    </span>
  )
}

interface Props {
  market: MarketSnapshot
}

const HEADERS = ['Símbolo', 'Precio', 'ROC %', 'RSI', 'ADX', '+DI', '−DI', 'ATR %', 'HTF', 'Régimen', 'Señal']

export default function MarketTable({ market }: Props) {
  return (
    <div className="bg-bg-card rounded-lg overflow-hidden">
      <div className="px-5 py-3.5 border-b border-line flex items-center justify-between">
        <h2 className="text-sm font-semibold text-tx-primary">Señales de Mercado</h2>
        <span className="text-tx-muted text-xs">{Object.keys(market).length} pares</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line">
              {HEADERS.map((h) => (
                <th key={h} className="px-5 py-3 text-left text-tx-muted text-xs font-medium whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(market).map(([symbol, data]) => {
              const base = symbol.replace('/USDT', '')
              const rocPos = data.roc !== null && data.roc > 0
              const rocNeg = data.roc !== null && data.roc < 0
              const trending = data.adx !== null && data.adx > 20
              const price = data.price?.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })

              return (
                <tr
                  key={symbol}
                  className="border-b border-line/40 hover:bg-bg-hover transition-colors duration-100"
                >
                  <td className="px-5 py-3.5">
                    <span className="font-semibold text-tx-primary">{base}</span>
                    <span className="text-tx-muted font-normal">/USDT</span>
                  </td>

                  <td className="px-5 py-3.5 font-num text-tx-primary">${price ?? '—'}</td>

                  <td className={`px-5 py-3.5 font-num font-medium ${rocPos ? 'text-brand-green' : rocNeg ? 'text-brand-red' : 'text-tx-muted'}`}>
                    {data.roc !== null ? `${data.roc >= 0 ? '+' : ''}${data.roc.toFixed(2)}%` : '—'}
                  </td>

                  <td className="px-5 py-3.5">
                    <RsiBar rsi={data.rsi} />
                  </td>

                  <td className="px-5 py-3.5">
                    <span className={`font-num font-medium ${trending ? 'text-brand-gold' : 'text-tx-secondary'}`}>
                      {fmt(data.adx)}
                      {trending && <span className="ml-1 text-[10px] text-brand-gold/70">TREND</span>}
                    </span>
                  </td>

                  <td className="px-5 py-3.5 font-num text-tx-secondary">{fmt(data.plus_di)}</td>
                  <td className="px-5 py-3.5 font-num text-tx-secondary">{fmt(data.minus_di)}</td>
                  <td className="px-5 py-3.5 font-num text-tx-muted text-xs">{fmt(data.atr_pct, 3)}%</td>

                  <td className="px-5 py-3.5">
                    <div className="flex flex-col items-start gap-0.5">
                      <HtfBadge trend={data.htf_trend} />
                      {data.htf_ema && (
                        <span className="text-[10px] text-tx-muted font-num">{data.htf_ema.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                      )}
                    </div>
                  </td>

                  <td className="px-5 py-3.5">
                    {data.regime === 'bull_run' ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-sm bg-brand-gold/10 text-brand-gold">
                        🚀 Bull Run
                      </span>
                    ) : data.regime === 'normal' ? (
                      <span className="text-xs text-brand-green font-medium">✅ Normal</span>
                    ) : (
                      <span className="text-tx-muted text-xs">—</span>
                    )}
                  </td>

                  <td className="px-5 py-3.5">
                    {data.regime === 'bull_run' ? (
                      <span className="text-tx-muted text-xs">pausado</span>
                    ) : (
                      <SignalBadge signal={data.signal} />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
