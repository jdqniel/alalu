import { useEffect, useState } from 'react'
import { openStream } from './api'
import type { MarketSnapshot, Portfolio } from './types'
import Navbar from './components/Navbar'
import MetricCard from './components/MetricCard'
import MarketTable from './components/MarketTable'
import PositionsPanel from './components/PositionsPanel'

const CAPITAL = 400

export default function App() {
  const [market, setMarket] = useState<MarketSnapshot>({})
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    const source = openStream(
      ({ market: m, portfolio: p }) => {
        setMarket(m)
        setPortfolio(p)
        setLastUpdated(new Date())
        setLoading(false)
        setError(false)
      },
      () => setError(true),
    )
    return () => source.close()
  }, [])

  const totalTrades = portfolio?.history.length ?? 0
  const wins = portfolio?.history.filter((t) => t.type === 'WIN ✅').length ?? 0
  const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0
  const isActive = !loading && !error && !!portfolio && !portfolio.circuit_breaker

  return (
    <div className="flex flex-col h-screen bg-bg-base text-tx-primary overflow-hidden">
      <Navbar
        isActive={isActive}
        circuitBreaker={portfolio?.circuit_breaker ?? false}
        lastUpdated={lastUpdated}
      />

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-tx-secondary">
          <div className="w-6 h-6 border-2 border-tx-muted border-t-brand-gold rounded-full animate-spin" />
          <p className="text-sm">Sincronizando con el motor...</p>
          {error && (
            <p className="text-xs text-brand-red mt-1">
              No se puede conectar. ¿Está corriendo api.py?
            </p>
          )}
        </div>
      ) : (
        <main className="flex-1 overflow-auto px-6 py-4">
          <div className="max-w-[1600px] mx-auto space-y-4">
            {/* Metric Cards */}
            <div className="grid grid-cols-4 gap-3">
              <MetricCard label="Capital Inicial" value={`$${CAPITAL.toFixed(2)}`} />
              <MetricCard
                label="Balance Spot 1x"
                value={`$${portfolio!.balance_1x.toFixed(2)}`}
                delta={((portfolio!.balance_1x - CAPITAL) / CAPITAL) * 100}
              />
              <MetricCard
                label="Balance Futures 5x"
                value={`$${portfolio!.balance_5x.toFixed(2)}`}
                delta={((portfolio!.balance_5x - CAPITAL) / CAPITAL) * 100}
                highlight
              />
              <MetricCard
                label="Win Rate"
                value={`${winRate.toFixed(1)}%`}
                subtitle={`${wins}W / ${totalTrades - wins}L · ${totalTrades} trades`}
              />
            </div>

            {/* Main Grid */}
            <div className="grid grid-cols-5 gap-3">
              <div className="col-span-3">
                <MarketTable market={market} />
              </div>
              <div className="col-span-2">
                <PositionsPanel
                  activeTrades={portfolio!.active_trades}
                  history={portfolio!.history}
                  market={market}
                />
              </div>
            </div>
          </div>
        </main>
      )}
    </div>
  )
}
