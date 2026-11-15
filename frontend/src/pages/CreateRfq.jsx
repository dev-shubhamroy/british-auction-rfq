import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createRfq } from '../api'
import Card from '../components/Card'
import { Field, inputClass } from '../components/FormField'
import { TRIGGER_LABELS, localInputToUtcIso, toLocalInputValue } from '../format'

const TRIGGER_HELP = {
  BID_RECEIVED: 'Any new bid inside the window extends the auction.',
  ANY_RANK_CHANGE: 'Extends only if a bid changes the supplier ranking.',
  L1_CHANGE: 'Extends only if the lowest bidder changes.',
}

function defaultForm() {
  const start = new Date()
  start.setSeconds(0, 0) // current minute, so the auction opens immediately
  const minutesFromStart = (minutes) => toLocalInputValue(new Date(start.getTime() + minutes * 60000))
  const pickup = new Date(start.getTime() + 7 * 86400000)

  return {
    reference_id: '',
    name: '',
    pickup_date: toLocalInputValue(pickup).slice(0, 10),
    bid_start_time: toLocalInputValue(start),
    bid_close_time: minutesFromStart(30),
    forced_close_time: minutesFromStart(60),
    british_auction_enabled: true,
    trigger_window_minutes: '10',
    extension_minutes: '5',
    trigger_type: 'L1_CHANGE',
  }
}

// Quick checks so the user gets instant feedback; the backend repeats them.
function validate(form) {
  const start = new Date(form.bid_start_time)
  const close = new Date(form.bid_close_time)
  const forced = new Date(form.forced_close_time)
  if (close <= start) return 'Bid close time must be after bid start time.'
  if (forced <= close) return 'Forced close time must be after bid close time.'
  if (close <= new Date()) return 'Bid close time must be in the future.'
  if (form.pickup_date < form.bid_close_time.slice(0, 10)) {
    return 'Pickup / service date cannot be before the bid close date.'
  }
  return ''
}

export default function CreateRfq() {
  const navigate = useNavigate()
  const [form, setForm] = useState(defaultForm)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function update(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm({ ...form, [field]: value })
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const problem = validate(form)
    if (problem) {
      setError(problem)
      return
    }

    setError('')
    setSubmitting(true)
    const british = form.british_auction_enabled
    try {
      const rfq = await createRfq({
        reference_id: form.reference_id,
        name: form.name,
        pickup_date: form.pickup_date,
        bid_start_time: localInputToUtcIso(form.bid_start_time),
        bid_close_time: localInputToUtcIso(form.bid_close_time),
        forced_close_time: localInputToUtcIso(form.forced_close_time),
        british_auction_enabled: british,
        trigger_window_minutes: british ? Number(form.trigger_window_minutes) : null,
        extension_minutes: british ? Number(form.extension_minutes) : null,
        trigger_type: british ? form.trigger_type : null,
      })
      navigate(`/rfqs/${rfq.id}`)
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Create RFQ</h1>
        <p className="text-sm text-slate-500">Times are in your local timezone.</p>
      </div>

      <Card title="RFQ details">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Reference ID">
            <input required maxLength={50} placeholder="RFQ-2026-014" value={form.reference_id} onChange={update('reference_id')} className={inputClass} />
          </Field>
          <Field label="Pickup / service date">
            <input required type="date" value={form.pickup_date} onChange={update('pickup_date')} className={inputClass} />
          </Field>
          <div className="sm:col-span-2">
            <Field label="RFQ name">
              <input required maxLength={200} placeholder="Nhava Sheva to Jebel Ali, 1x40ft HC" value={form.name} onChange={update('name')} className={inputClass} />
            </Field>
          </div>
        </div>
      </Card>

      <Card title="Auction schedule">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Bid start">
            <input required type="datetime-local" value={form.bid_start_time} onChange={update('bid_start_time')} className={inputClass} />
          </Field>
          <Field label="Bid close">
            <input required type="datetime-local" value={form.bid_close_time} onChange={update('bid_close_time')} className={inputClass} />
          </Field>
          <Field label="Forced bid close" hint="Hard limit. Must be after bid close.">
            <input required type="datetime-local" value={form.forced_close_time} onChange={update('forced_close_time')} className={inputClass} />
          </Field>
        </div>
      </Card>

      <Card title="British auction">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.british_auction_enabled} onChange={update('british_auction_enabled')} />
          Enable British auction (automatic time extensions)
        </label>

        {form.british_auction_enabled && (
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Trigger window X (minutes)" hint="Activity in the last X minutes before close is monitored.">
                <input required type="number" min="1" max="1440" value={form.trigger_window_minutes} onChange={update('trigger_window_minutes')} className={inputClass} />
              </Field>
              <Field label="Extension duration Y (minutes)" hint="Added to the close time when triggered.">
                <input required type="number" min="1" max="1440" value={form.extension_minutes} onChange={update('extension_minutes')} className={inputClass} />
              </Field>
            </div>
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-slate-600">Extension trigger</legend>
              <div className="space-y-2">
                {Object.entries(TRIGGER_LABELS).map(([value, label]) => (
                  <label key={value} className="flex items-start gap-2 rounded border border-slate-200 px-3 py-2 text-sm has-[:checked]:border-blue-600 has-[:checked]:bg-blue-50/50">
                    <input type="radio" name="trigger_type" value={value} checked={form.trigger_type === value} onChange={update('trigger_type')} className="mt-0.5" />
                    <span>
                      <span className="block font-medium text-slate-800">{label}</span>
                      <span className="block text-xs text-slate-500">{TRIGGER_HELP[value]}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        )}
      </Card>

      {error && <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="flex justify-end gap-2">
        <button type="button" onClick={() => navigate('/')} className="rounded border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50">
          Cancel
        </button>
        <button type="submit" disabled={submitting} className="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-60">
          {submitting ? 'Creating…' : 'Create RFQ'}
        </button>
      </div>
    </form>
  )
}
