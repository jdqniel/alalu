interface MetricCardProps {
  label: string
  value: string
  delta?: number
  subtitle?: string
  highlight?: boolean
}

export default function MetricCard({ label, value, delta, subtitle, highlight }: MetricCardProps) {
  const isPos = delta !== undefined && delta > 0
  const isNeg = delta !== undefined && delta < 0

  return (
    <div
      className={`bg-bg-card rounded-lg px-5 py-4 ${
        highlight ? 'ring-1 ring-brand-gold/25' : ''
      }`}
    >
      <p className="text-tx-muted text-xs font-medium uppercase tracking-wider mb-2">{label}</p>
      <p className="font-num text-2xl font-semibold text-tx-primary leading-none">{value}</p>
      {delta !== undefined && (
        <p
          className={`font-num text-sm mt-1.5 font-medium ${
            isPos ? 'text-brand-green' : isNeg ? 'text-brand-red' : 'text-tx-muted'
          }`}
        >
          {delta > 0 ? '+' : ''}
          {delta.toFixed(2)}%
        </p>
      )}
      {subtitle && <p className="text-tx-muted text-xs mt-1">{subtitle}</p>}
    </div>
  )
}
