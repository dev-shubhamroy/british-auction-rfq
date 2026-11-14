async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(errorMessage(body) || `Request failed (${response.status})`)
  }
  return body
}

// FastAPI returns either {"detail": "message"} for our own errors or
// {"detail": [{loc, msg}, ...]} for Pydantic validation errors.
function errorMessage(body) {
  if (!body?.detail) return null
  if (typeof body.detail === 'string') return body.detail
  return body.detail
    .map((item) => {
      const field = item.loc?.length > 1 ? item.loc[item.loc.length - 1] : null
      const message = item.msg.replace(/^Value error, /, '')
      return field ? `${field.replaceAll('_', ' ')}: ${message}` : message
    })
    .join('. ')
}

export const getRfqs = () => request('/rfqs')
export const getRfq = (id) => request(`/rfqs/${id}`)
export const createRfq = (data) => request('/rfqs', { method: 'POST', body: JSON.stringify(data) })
export const submitBid = (rfqId, data) =>
  request(`/rfqs/${rfqId}/bids`, { method: 'POST', body: JSON.stringify(data) })
export const getSuppliers = () => request('/suppliers')
