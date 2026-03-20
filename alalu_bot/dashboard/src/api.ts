import type { MarketSnapshot, Portfolio } from './types'

export type StreamPayload = { market: MarketSnapshot; portfolio: Portfolio }

export function openStream(
  onData: (payload: StreamPayload) => void,
  onError: () => void,
): EventSource {
  const source = new EventSource('/api/stream')
  source.onmessage = (e) => {
    try {
      onData(JSON.parse(e.data))
    } catch {}
  }
  source.onerror = onError
  return source
}
