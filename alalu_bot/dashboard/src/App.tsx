import { useEffect, useState } from 'react'
import { openStream } from './api'
import type { MarketSnapshot, Portfolio, TradeEntry } from './types'
import Navbar from './components/Navbar'
import MetricCard from './components/MetricCard'
import MarketTable from './components/MarketTable'
import PositionsPanel from './components/PositionsPanel'
import EquityChart from './components/EquityChart'
import PnlChart from './components/PnlChart'
import StatsPanel from './components/StatsPanel'

const CAPITAL = 400

export default function App() {
  const [market, setMarket] = useState<MarketSnapshot>({})
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [trades, setTrades] = useState<TradeEntry[]>([])
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    const source = openStream(
      ({ market: m, portfolio: p, trades: t }) => {
        setMarket(m)
        setPortfolio(p)
        setTrades(t)
        setLastUpdated(new Date())
        setLoading(false)
        setError(false)
      },
      () => setError(true),
    )
    return () => source.close()
  }, [])

  const totalTrades = trades.length
  const wins = trades.filter((t) => parseFloat(t.pnl_usd) > 0).length
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

            {/* Market + Positions */}
            <div className="grid grid-cols-5 gap-3">
              <div className="col-span-3">
                <MarketTable market={market} />
              </div>
              <div className="col-span-2">
                <PositionsPanel
                  activeTrades={portfolio!.active_trades}
                  trades={trades}
                  market={market}
                />
              </div>
            </div>

            {/* Equity Curve + Stats */}
            <div className="grid grid-cols-5 gap-3">
              <div className="col-span-3">
                <EquityChart trades={trades} capital={CAPITAL} />
              </div>
              <div className="col-span-2">
                <StatsPanel trades={trades} capital={CAPITAL} />
              </div>
            </div>

            {/* PnL por Trade */}
            <PnlChart trades={trades} />
          </div>
        </main>
      )}
    </div>
  )
}
