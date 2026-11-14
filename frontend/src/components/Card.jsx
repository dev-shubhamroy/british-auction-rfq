export default function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`rounded-md border border-slate-200 bg-white ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}
