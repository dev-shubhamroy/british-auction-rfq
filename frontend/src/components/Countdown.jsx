import { useEffect, useState } from 'react'
import { formatCountdown } from '../format'

// Display-only timer. `serverOffsetMs` corrects for the browser clock being
// off from the server clock; the backend still decides whether a bid is on time.
export default function Countdown({ target, serverOffsetMs, onExpire }) {
  const [now, setNow] = useState(() => Date.now() + serverOffsetMs)

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() + serverOffsetMs), 1000)
    return () => clearInterval(timer)
  }, [serverOffsetMs])

  const remaining = new Date(target).getTime() - now

  useEffect(() => {
    if (remaining <= 0 && onExpire) onExpire()
    // Only fire when we cross zero, not on every tick afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining <= 0])

  return <span className="font-mono tabular-nums">{formatCountdown(remaining)}</span>
}
