const STYLES = {
  SCHEDULED: 'bg-slate-100 text-slate-700 ring-slate-300',
  ACTIVE: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  CLOSED: 'bg-slate-100 text-slate-600 ring-slate-200',
  FORCE_CLOSED: 'bg-amber-50 text-amber-800 ring-amber-200',
}

const LABELS = {
  SCHEDULED: 'Scheduled',
  ACTIVE: 'Active',
  CLOSED: 'Closed',
  FORCE_CLOSED: 'Force Closed',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  )
}
