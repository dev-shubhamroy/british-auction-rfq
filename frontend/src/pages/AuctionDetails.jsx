import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getRfq } from '../api'
import BidForm from '../components/BidForm'
import Card from '../components/Card'
import Countdown from '../components/Countdown'
import StatusBadge from '../components/StatusBadge'
import { TRIGGER_LABELS, formatDate, formatDateTime, formatMoney, formatTime } from '../format'

const REFRESH_MS = 5000

const EVENT_LABELS = {
  RFQ_CREATED: 'RFQ created',
  BID_SUBMITTED: 'Bid submitted',
  RANK_CHANGED: 'Ranking changed',
  L1_CHANGED: 'L1 changed',
  AUCTION_EXTENDED: 'Auction extended',
  AUCTION_CLOSED: 'Auction closed',
  AUCTION_FORCE_CLOSED: 'Force closed',
}

const EVENT_COLORS = {
  AUCTION_EXTENDED: 'text-blue-700',
  L1_CHANGED: 'text-emerald-700',
  AUCTION_CLOSED: 'text-slate-900',
  AUCTION_FORCE_CLOSED: 'text-amber-700',
}

export default function AuctionDetails() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [serverOffsetMs, setServerOffsetMs] = useState(0)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const detail = await getRfq(id)
      setServerOffsetMs(new Date(detail.server_time).getTime() - Date.now())
      setData(detail)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [id])

  useEffect(() => {
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  if (!data) {
    return error ? <ErrorBox message={error} /> : <p className="text-sm text-slate-500">Loading…</p>
  }

  const { rfq, status } = data
  const countdownTarget = status === 'SCHEDULED' ? rfq.bid_start_time : rfq.current_close_time

  return (
    <div className="space-y-4">
      <div>
        <Link to="/" className="text-sm text-blue-700 hover:underline">← All auctions</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-lg font-semibold text-slate-900">{rfq.name}</h1>
          <StatusBadge status={status} />
        </div>
        <p className="font-mono text-xs text-slate-500">{rfq.reference_id}</p>
      </div>

      {error && <ErrorBox message={`Could not refresh: ${error}`} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Current lowest bid" value={formatMoney(data.lowest_bid)} />
        <Stat
          label={status === 'SCHEDULED' ? 'Starts in' : 'Time remaining'}
          value={
            status === 'SCHEDULED' || status === 'ACTIVE' ? (
              <Countdown target={countdownTarget} serverOffsetMs={serverOffsetMs} onExpire={load} />
            ) : (
              'Closed'
            )
          }
        />
        <Stat
          label="Current close time"
          value={formatDateTime(rfq.current_close_time)}
          note={
            data.extension_count > 0
              ? `Extended ${data.extension_count}× · originally ${formatDateTime(rfq.bid_close_time)}`
              : null
          }
        />
        <Stat label="Forced close time" value={formatDateTime(rfq.forced_close_time)} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 space-y-4 xl:col-span-2">
          <Card title="Supplier rankings">
            <BidTable rows={data.rankings} showRank emptyText="No bids yet." />
          </Card>
          <Card title={`Bid history (${data.bids.length})`}>
            <p className="mb-3 text-xs text-slate-500">Every bid received, sorted by total price.</p>
            <BidTable rows={data.bids} emptyText="No bids yet." />
          </Card>
        </div>

        <div className="min-w-0 space-y-4">
          <Card title="Submit a bid">
            <BidForm rfqId={rfq.id} isOpen={status === 'ACTIVE'} onSubmitted={load} />
          </Card>
          <Card title="RFQ & auction configuration">
            <dl className="space-y-2 text-sm">
              <Row label="Pickup / service date" value={formatDate(rfq.pickup_date)} />
              <Row label="Bid start" value={formatDateTime(rfq.bid_start_time)} />
              <Row label="Original close" value={formatDateTime(rfq.bid_close_time)} />
              <Row label="Forced close" value={formatDateTime(rfq.forced_close_time)} />
              <Row label="British auction" value={rfq.british_auction_enabled ? 'Enabled' : 'Disabled'} />
              {rfq.british_auction_enabled && (
                <>
                  <Row label="Trigger window (X)" value={`${rfq.trigger_window_minutes} min`} />
                  <Row label="Extension duration (Y)" value={`${rfq.extension_minutes} min`} />
                  <Row label="Extension trigger" value={TRIGGER_LABELS[rfq.trigger_type]} />
                </>
              )}
            </dl>
          </Card>
        </div>
      </div>

      <Card title="Activity log">
        <ActivityLog entries={data.activity} />
      </Card>
    </div>
  )
}

function BidTable({ rows, showRank = false, emptyText }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500">{emptyText}</p>
  return (
    <div className="-mx-4 overflow-x-auto px-1">
      <table className="min-w-full text-sm">
        <thead className="text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr className="border-b border-slate-200">
            {showRank && <th className="px-3 py-2">Rank</th>}
            <th className="px-3 py-2">Supplier</th>
            <th className="px-3 py-2">Carrier</th>
            <th className="px-3 py-2 text-right">Freight</th>
            <th className="px-3 py-2 text-right">Origin</th>
            <th className="px-3 py-2 text-right">Destination</th>
            <th className="px-3 py-2 text-right">Total</th>
            <th className="px-3 py-2 text-right">Transit</th>
            <th className="px-3 py-2">Valid until</th>
            <th className="px-3 py-2">Submitted</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.id} className={showRank && row.rank === 1 ? 'bg-emerald-50/60' : ''}>
              {showRank && <td className="px-3 py-2 font-semibold">L{row.rank}</td>}
              <td className="whitespace-nowrap px-3 py-2">{row.supplier_name}</td>
              <td className="whitespace-nowrap px-3 py-2">{row.carrier_name}</td>
              <td className="whitespace-nowrap px-3 py-2 text-right">{formatMoney(row.freight_charges)}</td>
              <td className="whitespace-nowrap px-3 py-2 text-right">{formatMoney(row.origin_charges)}</td>
              <td className="whitespace-nowrap px-3 py-2 text-right">{formatMoney(row.destination_charges)}</td>
              <td className="whitespace-nowrap px-3 py-2 text-right font-medium">{formatMoney(row.total_amount)}</td>
              <td className="whitespace-nowrap px-3 py-2 text-right">{row.transit_time_days} d</td>
              <td className="whitespace-nowrap px-3 py-2">{formatDate(row.quote_validity_date)}</td>
              <td className="whitespace-nowrap px-3 py-2 text-slate-500">{formatDateTime(row.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ActivityLog({ entries }) {
  return (
    <ol className="divide-y divide-slate-100">
      {entries.map((entry) => (
        <li key={entry.id} className="flex flex-col gap-1 py-2 text-sm sm:flex-row sm:gap-4">
          <span className="w-44 shrink-0 text-slate-500">{formatDateTime(entry.created_at)}</span>
          <span className={`w-36 shrink-0 font-medium ${EVENT_COLORS[entry.event_type] ?? 'text-slate-700'}`}>
            {EVENT_LABELS[entry.event_type]}
          </span>
          <span className="text-slate-700">
            {entry.message}
            {entry.previous_close_time && (
              <span className="ml-1 text-slate-500">
                Close time {formatTime(entry.previous_close_time)} → {formatTime(entry.new_close_time)}.
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1 text-base font-semibold text-slate-900">{value}</div>
      {note && <div className="mt-0.5 text-xs text-blue-700">{note}</div>}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-900">{value}</dd>
    </div>
  )
}

function ErrorBox({ message }) {
  return <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>
}
