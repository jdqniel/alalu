import type { MarketSnapshot, Portfolio } from './types'

export async function fetchMarket(): Promise<MarketSnapshot> {
  const res = await fetch('/api/market')
  if (!res.ok) throw new Error('market fetch failed')
  return res.json()
}

export async function fetchPortfolio(): Promise<Portfolio> {
  const res = await fetch('/api/portfolio')
  if (!res.ok) throw new Error('portfolio fetch failed')
  return res.json()
}
