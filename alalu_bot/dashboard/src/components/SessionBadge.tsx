import { useEffect, useState } from 'react'

const SESSION_START = 13
const SESSION_END = 21

function getInfo() {
  const now = new Date()
  const totalMin = now.getUTCHours() * 60 + now.getUTCMinutes()
  const start = SESSION_START * 60
  const end = SESSION_END * 60
  const inSession = totalMin >= start && totalMin < end

  if (inSession) {
    const rem = end - totalMin
    return { inSession: true, time: `${Math.floor(rem / 60)}h ${rem % 60}m restante` }
  }
  const toNext = totalMin < start ? start - totalMin : 24 * 60 - totalMin + start
  return { inSession: false, time: `abre en ${Math.floor(toNext / 60)}h ${toNext % 60}m` }
}

export default function SessionBadge() {
  const [info, setInfo] = useState(getInfo)

  useEffect(() => {
    const id = setInterval(() => setInfo(getInfo()), 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div
      className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border ${
        info.inSession
          ? 'bg-brand-green/5 border-brand-green/20 text-brand-green'
          : 'bg-bg-elevated border-line text-tx-muted'
      }`}
    >
      <div
        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
          info.inSession ? 'bg-brand-green blink' : 'bg-tx-muted'
        }`}
      />
      <span className="font-medium whitespace-nowrap">
        {info.inSession ? 'Sesión Activa' : 'Fuera de Sesión'}
      </span>
      <span className="opacity-60 whitespace-nowrap">{info.time}</span>
    </div>
  )
}
