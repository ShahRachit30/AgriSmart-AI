// Thin API client. All calls are same-origin (FastAPI serves this bundle), so no
// CORS and no hard-coded localhost - the app works behind any proxy/preview host.

const j = async (res) => {
  let body = null
  try {
    body = await res.json()
  } catch {
    body = { ok: false, message: `Server returned ${res.status}` }
  }
  if (!res.ok && body && !body.message) body.message = `Request failed (${res.status})`
  return body
}

// Every read that returns prose takes the UI language, so switching language
// refetches the same numbers with translated text (the slugs never change).
const L = (lang) => `language=${encodeURIComponent(lang || 'en')}`

export const getHealth = () => fetch('/api/health').then(j)
export const getMeta = () => fetch('/api/meta').then(j)
export const getMetrics = (lang = 'en') => fetch(`/api/metrics?${L(lang)}`).then(j)
export const getSensors = (device, lang = 'en') =>
  fetch(`/api/sensors/latest?device_id=${encodeURIComponent(device)}&${L(lang)}`).then(j)
export const getSensorHistory = (device, samples = 24, lang = 'en') =>
  fetch(`/api/sensors/history?device_id=${encodeURIComponent(device)}&samples=${samples}&${L(lang)}`).then(j)
export const getDevices = (lang = 'en') => fetch(`/api/sensors/devices?${L(lang)}`).then(j)
export const getSamples = (lang = 'en') => fetch(`/api/samples?${L(lang)}`).then(j)

export const postWeather = (payload) =>
  fetch('/api/weather', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(j)

export const postCrop = (payload) =>
  fetch('/api/recommend-crop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(j)

export const postAssistant = (question, context, language) =>
  fetch('/api/assistant', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, context, language }),
  }).then(j)

export async function postAnalyze({ file, fields }) {
  const fd = new FormData()
  if (file) fd.append('image', file)
  Object.entries(fields).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) fd.append(k, v)
  })
  const res = await fetch('/api/analyze', { method: 'POST', body: fd })
  return j(res)
}

// Re-render an analysis we already have in another language. The server replays the
// stored prediction (no model run), so the numbers do not change - only the words.
export const postRelocalize = (sessionId, language) =>
  fetch('/api/relocalize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, language }),
  }).then(j)
