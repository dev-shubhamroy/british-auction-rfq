import { useEffect, useState } from 'react'
import { getSuppliers, submitBid } from '../api'
import { formatMoney, formatTime } from '../format'
import { Field, inputClass } from './FormField'

const EMPTY_FORM = {
  supplier_id: '',
  carrier_name: '',
  freight_charges: '',
  origin_charges: '0',
  destination_charges: '0',
  transit_time_days: '',
  quote_validity_date: '',
}

export default function BidForm({ rfqId, isOpen, onSubmitted }) {
  const [suppliers, setSuppliers] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    getSuppliers().then(setSuppliers).catch((err) => setError(err.message))
  }, [])

  const total =
    (Number(form.freight_charges) || 0) +
    (Number(form.origin_charges) || 0) +
    (Number(form.destination_charges) || 0)

  function update(field) {
    return (event) => setForm({ ...form, [field]: event.target.value })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setResult(null)
    setSubmitting(true)
    try {
      const response = await submitBid(rfqId, {
        ...form,
        supplier_id: Number(form.supplier_id),
        transit_time_days: Number(form.transit_time_days),
      })
      setResult(response)
      // Keep supplier/carrier/transit/validity so the supplier can quickly re-bid lower.
      setForm((current) => ({ ...current, freight_charges: '' }))
      onSubmitted()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!isOpen) {
    return <p className="text-sm text-slate-500">Bidding is not open for this auction.</p>
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Field label="Supplier">
        <select required value={form.supplier_id} onChange={update('supplier_id')} className={inputClass}>
          <option value="">Select supplier</option>
          {suppliers.map((supplier) => (
            <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
          ))}
        </select>
      </Field>
      <Field label="Carrier name">
        <input required value={form.carrier_name} onChange={update('carrier_name')} className={inputClass} />
      </Field>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Freight">
          <input required type="number" min="0.01" step="0.01" value={form.freight_charges} onChange={update('freight_charges')} className={inputClass} />
        </Field>
        <Field label="Origin">
          <input required type="number" min="0" step="0.01" value={form.origin_charges} onChange={update('origin_charges')} className={inputClass} />
        </Field>
        <Field label="Destination">
          <input required type="number" min="0" step="0.01" value={form.destination_charges} onChange={update('destination_charges')} className={inputClass} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Transit time (days)">
          <input required type="number" min="1" step="1" value={form.transit_time_days} onChange={update('transit_time_days')} className={inputClass} />
        </Field>
        <Field label="Quote valid until">
          <input required type="date" value={form.quote_validity_date} onChange={update('quote_validity_date')} className={inputClass} />
        </Field>
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
        <span className="text-slate-500">Total quote</span>
        <span className="font-semibold">{formatMoney(total)}</span>
      </div>

      {error && <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {result && (
        <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Bid accepted. Current rank: L{result.rank}.
          {result.extended && ` Auction extended to ${formatTime(result.current_close_time)}.`}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-60"
      >
        {submitting ? 'Submitting…' : 'Submit bid'}
      </button>
    </form>
  )
}
