import SessionBadge from './SessionBadge'

interface NavbarProps {
  isActive: boolean
  circuitBreaker: boolean
  lastUpdated: Date | null
}

export default function Navbar({ isActive, circuitBreaker, lastUpdated }: NavbarProps) {
  return (
    <nav className="h-14 bg-bg-card border-b border-line flex items-center px-6 gap-4 shrink-0">
      <div className="flex items-center gap-1.5">
        <span className="text-brand-gold font-bold text-base tracking-widest">ALALU</span>
        <span className="text-tx-muted text-xs font-medium tracking-wider">BOT</span>
      </div>

      <div className="w-px h-5 bg-line" />

      <div className="flex items-center gap-2">
        <div
          className={`w-1.5 h-1.5 rounded-full ${
            circuitBreaker ? 'bg-brand-red' : isActive ? 'bg-brand-green blink' : 'bg-tx-muted'
          }`}
        />
        <span className="text-xs font-medium">
          {circuitBreaker ? (
            <span className="text-brand-red">Circuit Breaker</span>
          ) : isActive ? (
            <span className="text-brand-green">Motor Activo</span>
          ) : (
            <span className="text-tx-secondary">Sincronizando...</span>
          )}
        </span>
      </div>

      {circuitBreaker && (
        <div className="bg-brand-red/10 border border-brand-red/30 text-brand-red text-xs px-3 py-1 rounded-md">
          🚨 Trading detenido — Balance cayó al 80%
        </div>
      )}

      <div className="ml-auto flex items-center gap-3">
        <SessionBadge />
        <div className="w-px h-4 bg-line" />
        <span className="text-tx-muted text-xs font-mono">
          {lastUpdated ? lastUpdated.toLocaleTimeString() : '—'}
        </span>
      </div>
    </nav>
  )
}
