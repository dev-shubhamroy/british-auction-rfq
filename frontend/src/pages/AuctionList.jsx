import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getRfqs } from '../api'
import StatusBadge from '../components/StatusBadge'
import { formatDateTime, formatMoney } from '../format'

const REFRESH_MS = 10000

export default function AuctionList() {
  const [rfqs, setRfqs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await getRfqs()
        if (!cancelled) {
          setRfqs(data.items)
          setError('')
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">British Auctions</h1>
          <p className="text-sm text-slate-500">All RFQs and their current auction state.</p>
        </div>
        <Link to="/rfqs/new" className="rounded bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-800">
          Create RFQ
        </Link>
      </div>

      {error && <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="whitespace-nowrap bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2.5">RFQ ID</th>
              <th className="px-4 py-2.5">RFQ name</th>
              <th className="px-4 py-2.5 text-right">Lowest bid</th>
              <th className="px-4 py-2.5 text-right">Bids</th>
              <th className="px-4 py-2.5">Current close</th>
              <th className="px-4 py-2.5">Forced close</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rfqs?.map((rfq) => (
              <tr key={rfq.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs">{rfq.reference_id}</td>
                <td className="px-4 py-2.5">{rfq.name}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">{formatMoney(rfq.lowest_bid)}</td>
                <td className="px-4 py-2.5 text-right">{rfq.bid_count}</td>
                <td className="whitespace-nowrap px-4 py-2.5">
                  {formatDateTime(rfq.current_close_time)}
                  {rfq.current_close_time !== rfq.bid_close_time && (
                    <span className="ml-1.5 text-xs text-blue-700">extended</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5">{formatDateTime(rfq.forced_close_time)}</td>
                <td className="px-4 py-2.5"><StatusBadge status={rfq.status} /></td>
                <td className="px-4 py-2.5 text-right">
                  <Link to={`/rfqs/${rfq.id}`} className="text-blue-700 hover:underline">View</Link>
                </td>
              </tr>
            ))}
            {rfqs?.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                  No RFQs yet. <Link to="/rfqs/new" className="text-blue-700 hover:underline">Create one</Link>.
                </td>
              </tr>
            )}
            {rfqs === null && !error && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500">Loading…</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
