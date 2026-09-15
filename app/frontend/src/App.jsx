import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LANG_LABEL, LANGS, makeT } from './i18n.js'
import * as api from './api.js'

/* ------------------------------------------------------------------ hooks */
function useAsync(fn, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null })
  useEffect(() => {
    let live = true
    setState((s) => ({ ...s, loading: true }))
    fn()
      .then((data) => live && setState({ loading: false, data, error: data?.ok === false ? data.message : null }))
      .catch((e) => live && setState({ loading: false, data: null, error: String(e) }))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

/* --------------------------------------------------------------- widgets */
// Injected by vite.config.js at build time; falls back to the API-stamped id.
const BUILD_LABEL = (typeof __BUILD_ID__ !== 'undefined' && __BUILD_ID__) || 'dev'

const num = (v, digits = 1) => (v === null || v === undefined || v === '' ? '—' : Number(v).toFixed(digits))
const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(Number(v) * 100)}%`)

function Donut({ value = 0, grade = '—', color = '#2e8b45', size = 118, label, gradeWord }) {
  const r = (size - 14) / 2
  const c = 2 * Math.PI * r
  const filled = Math.max(0, Math.min(100, Number(value) || 0)) / 100
  return (
    <svg className="donut" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={label || `sustainability score ${value} of 100`}>
      <circle className="bg" cx={size / 2} cy={size / 2} r={r} />
      <circle className="fg" cx={size / 2} cy={size / 2} r={r} stroke={color}
        strokeDasharray={`${c * filled} ${c}`} />
      <text x="50%" y="47%" textAnchor="middle" transform={`rotate(90 ${size / 2} ${size / 2})`}
        fontSize="24" fontWeight="800" fill="#0d2b16">{Math.round(value)}</text>
      <text x="50%" y="64%" textAnchor="middle" transform={`rotate(90 ${size / 2} ${size / 2})`}
        fontSize="12" fill="#6b7f70">{gradeWord || 'grade'} {grade}</text>
    </svg>
  )
}

function Sparkline({ points = [], color = '#2e8b45', width = 240, height = 48, min, max, label }) {
  if (!points.length) return null
  const lo = min ?? Math.min(...points)
  const hi = max ?? Math.max(...points)
  const span = hi - lo || 1
  const step = points.length > 1 ? width / (points.length - 1) : width
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${i * step} ${height - ((p - lo) / span) * height}`).join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
      role="img" aria-label={label || 'trend'}>
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  )
}

function Card({ title, step, children, aside }) {
  return (
    <section className="card">
      <h2>
        {step ? <span className="step">{step}</span> : null}
        {title}
        {aside ? <span style={{ marginLeft: 'auto' }}>{aside}</span> : null}
      </h2>
      {children}
    </section>
  )
}

function Alert({ kind = 'warn', children }) {
  return <div className={`alert ${kind === 'info' ? 'info' : kind === 'bad' ? 'bad' : ''}`}>{children}</div>
}

// Progressive disclosure. This is a native <details> on purpose: the children stay
// in the DOM (so the language-switch checks and screen readers still see them) while
// the screen itself only shows what is needed for the task at hand.
function Fold({ label, children, open }) {
  return (
    <details className="fold" {...(open ? { open: true } : null)}>
      <summary><span className="chev" aria-hidden="true">▸</span>{label}</summary>
      <div className="fold-body">{children}</div>
    </details>
  )
}

// One number from the at-a-glance strip. Label above, value below.
function Stat({ label, value, tone }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <b className={tone || ''}>{value}</b>
    </div>
  )
}

/* ------------------------------------------------------------------- app */
const SAMPLE = { N: 50.55, P: 53.36, K: 48.15, temperature: 25.62, humidity: 71.48, ph: 6.47, rainfall: 103.46 }

// Upload limits: one source of truth for the whole file.
const MAX_MB = 25        // keep in sync with MAX_UPLOAD_BYTES in app/backend/main.py
const MAX_SIDE = 1600    // longest side we downscale to in the browser before upload

export default function App() {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('agrismart.lang') || 'en' } catch { return 'en' }
  })
  const [view, setView] = useState('dashboard')
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)              // dimensions / source size
  const [uploadNote, setUploadNote] = useState(null)  // "preparing" / "compressed" note
  const [previewBroken, setPreviewBroken] = useState(false)
  const fileRef = useRef(null)
  const [analysis, setAnalysis] = useState(null)
  const [device, setDevice] = useState('esp32-field-1')
  const [form, setForm] = useState({
    soil_moisture_pct: 24, soil_ph: 6.5, city: 'Ahmedabad', planted_crop: 'tomato',
    area_ha: 1.2, ...SAMPLE, use_sensors: true,
  })
  const [chat, setChat] = useState([])
  const [question, setQuestion] = useState('')

  const t = useMemo(() => makeT(lang), [lang])
  const [relocalizing, setRelocalizing] = useState(false)
  // localStorage can throw in sandboxed iframes (SecurityError) - never let that
  // break the app.
  useEffect(() => {
    try { localStorage.setItem('agrismart.lang', lang) } catch { /* ignore */ }
    try { document.documentElement.lang = lang } catch { /* ignore */ }
  }, [lang])

  // Every server-read that returns prose is keyed on the language as well, so the
  // selector re-renders the WHOLE page: cards refetch, the analysis re-localizes.
  // The checkpoint loads in a background thread at startup, so a page opened in the
  // first seconds would otherwise report "model not trained" for good. Poll a few
  // times until the warm-up finishes (or a real load error is reported).
  const [healthTick, setHealthTick] = useState(0)
  const health = useAsync(api.getHealth, [healthTick])
  const meta = useAsync(api.getMeta, [])
  const sensors = useAsync(() => api.getSensors(device, lang), [device, lang])
  const history = useAsync(() => api.getSensorHistory(device, 24, lang), [device, lang])
  const metrics = useAsync(() => api.getMetrics(lang), [lang])
  const samples = useAsync(() => api.getSamples(lang).catch(() => null), [lang])

  useEffect(() => {
    if (!health.data || health.data.model_available || health.data.model?.error) return
    if (healthTick >= 8) return
    const id = setTimeout(() => setHealthTick((n) => n + 1), 1500)
    return () => clearTimeout(id)
  }, [health.data, healthTick])

  // Some embedded webviews (and jsdom) have no scrollTo - never let that kill a render.
  const scrollTop = () => { try { window.scrollTo({ top: 0, behavior: 'smooth' }) } catch { /* ignore */ } }

  const setField = (k) => (e) => {
    const raw = e?.target ? e.target.value : e
    setForm((f) => ({ ...f, [k]: raw }))
  }

  // Upload limits live at MODULE scope: both App (which prepares the file) and the
  // Dashboard card (which prints "<= 25 MB") must read the same numbers. When they
  // were App-local, Dashboard could not see them and threw on render -> blank page.

  const prepareFile = async (f) => {
    try {
      let bmp = null
      if (window.createImageBitmap) {
        try { bmp = await createImageBitmap(f) } catch { bmp = null }
      }
      if (!bmp) return { file: f, note: null }        // e.g. HEIC: let the server decode it
      const { width: w0, height: h0 } = bmp
      const scale = Math.min(1, MAX_SIDE / Math.max(w0, h0))
      if (scale === 1 && f.size < 2.5 * 1024 * 1024) return { file: f, note: { w: w0, h: h0 } }
      const w = Math.max(1, Math.round(w0 * scale))
      const h = Math.max(1, Math.round(h0 * scale))
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      canvas.getContext('2d').drawImage(bmp, 0, 0, w, h)
      const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.9))
      if (!blob || blob.size >= f.size) return { file: f, note: { w: w0, h: h0 } }
      const out = new File([blob], (f.name || 'leaf').replace(/\.[^.]+$/, '') + '.jpg',
        { type: 'image/jpeg' })
      return { file: out, note: { w: w0, h: h0, w2: w, h2: h, from: f.size, to: out.size } }
    } catch {
      return { file: f, note: null }
    }
  }

  const onPick = async (f) => {
    if (!f) return
    setError(null)
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`${t('err_size')} (${(f.size / 1024 / 1024).toFixed(1)} MB > ${MAX_MB} MB)`)
      return
    }
    setBusy(true)
    setUploadNote(t('upload_preparing'))
    try {
      const { file: prepared, note } = await prepareFile(f)
      if (previewUrl?.startsWith('blob:')) URL.revokeObjectURL(previewUrl)
      setFile(prepared)
      setInfo(note)
      setPreviewUrl(URL.createObjectURL(prepared))
      setPreviewBroken(false)
      setUploadNote(note?.from
        ? `${t('upload_compressed')}: ${(note.from / 1024 / 1024).toFixed(1)} MB to ${(note.to / 1024 / 1024).toFixed(1)} MB`
        : null)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const clearFile = () => {
    if (previewUrl?.startsWith('blob:')) URL.revokeObjectURL(previewUrl)
    setFile(null); setPreviewUrl(null); setError(null)
    setInfo(null); setUploadNote(null); setPreviewBroken(false)
  }

  const openPicker = () => {
    const el = fileRef.current
    if (el) el.click()
    else setError(t('err_picker'))
  }

  // NOTE: always call this as analyze() or analyze({ sampleId }). Passing it
  // directly to onClick would hand it the click event - the guard below ignores
  // anything that is not a real sample id string, and the file is never dropped
  // unless a bundled sample was genuinely requested.
  const analyze = async (opts = {}) => {
    const sampleId = (opts && typeof opts === 'object' && typeof opts.sampleId === 'string')
      ? opts.sampleId
      : null
    setBusy(true); setError(null)
    if (sampleId) {
      // bundled sample: no local file, the API reads it from disk
      if (previewUrl?.startsWith('blob:')) URL.revokeObjectURL(previewUrl)
      setFile(null)
      setPreviewUrl(`/api/samples/${encodeURIComponent(sampleId)}/image`)
    }
    const fields = {
      language: lang,
      sample_id: sampleId,
      soil_moisture_pct: form.soil_moisture_pct,
      soil_ph: form.soil_ph,
      city: form.city,
      planted_crop: form.planted_crop,
      area_ha: form.area_ha,
      nitrogen: form.N, phosphorus: form.P, potassium: form.K,
      temperature: form.temperature, humidity: form.humidity, rainfall: form.rainfall,
      use_sensors: form.use_sensors,
    }
    try {
      const res = await api.postAnalyze({ file, fields })
      if (res.ok === false) {
        const msg = res.message || 'Analysis failed'
        setError(res.hint ? `${msg} — ${res.hint}` : msg)
        scrollTop()   // make the banner visible
      }
      if (res.session_id) {
        setAnalysis(res)
        setChat([])
        setView('results')
        scrollTop()
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const ask = useCallback(async (q) => {
    const question_ = (q ?? question).trim()
    if (!question_) return
    setChat((c) => [...c, { role: 'user', text: question_ }])
    setQuestion('')
    const ctx = analysis
      ? Object.fromEntries(['prediction', 'risk', 'irrigation', 'weather', 'sustainability',
        'crop_recommendation', 'sensors'].map((k) => [k, analysis[k]]))
      : {}
    try {
      const res = await api.postAssistant(question_, ctx, lang)
      setChat((c) => [...c, { role: 'bot', text: res.answer || res.message, sources: res.sources, intent: res.intent }])
    } catch (e) {
      setChat((c) => [...c, { role: 'bot', text: String(e), sources: [] }])
    }
  }, [question, analysis, lang])

  const modelOk = health.data?.model_available

  // One handler for the whole language switch:
  //  1. flip the tag -> every t() string redraws, the read-only cards refetch with
  //     `language=...` (sensors / history / metrics / samples);
  //  2. if an analysis is on screen, ask the server to re-render it. The model is
  //     NOT re-run - the stored prediction is replayed, so the numbers the farmer
  //     just read stay identical and only the wording changes.
  const changeLang = useCallback(async (next) => {
    if (!next || next === lang) return
    setLang(next)
    const sid = analysis?.session_id
    if (!sid) return
    setRelocalizing(true)
    setChat([])                       // stale-language answers would be confusing
    try {
      const res = await api.postRelocalize(sid, next)
      if (res.ok !== false && res.session_id) {
        setAnalysis(res)
        setChat([])
      } else if (res.message) {
        setError(res.message)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setRelocalizing(false)
    }
  }, [lang, analysis])

  /* ------------------------------------------------------------- render */
  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <div className="logo" aria-hidden>🌿</div>
          <div>
            <h1>{t('app_name')}</h1>
            <p>{t('tagline')}</p>
          </div>
        </div>

        <span className={`pill ${modelOk ? '' : 'bad'}`}>
          <span className="dot" /> {modelOk
            ? t('model_ready', { m: health.data?.model?.model_name || '' })
            : t('demo_mode')}
        </span>

        <nav className="tabs" aria-label="views">
          <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>{t('dashboard')}</button>
          <button className={view === 'results' ? 'active' : ''} onClick={() => setView('results')}>{t('results')}</button>
        </nav>

        <div className="lang">
          {LANGS.map((l) => (
            <button key={l} className={l === lang ? 'active' : ''} onClick={() => changeLang(l)}
              title={t('switch_note')} aria-pressed={l === lang}>
              {LANG_LABEL[l]}
            </button>
          ))}
        </div>
      </header>

      <main>
        {error && <div className="banner"><Alert kind="bad">{error}</Alert></div>}
        {!modelOk && health.data && (
          <div className="banner"><Alert kind="info">{t('demo_mode')} {health.data.model?.error}</Alert></div>
        )}

        {view === 'dashboard'
          ? <Dashboard {...{ t, lang, form, setField, setForm, file, previewUrl, onPick, openPicker,
            fileRef, clearFile, info, uploadNote, previewBroken, setPreviewBroken,
            analyze, busy, sensors, history, device, setDevice, meta, metrics, samples: samples.data,
            weather: analysis?.weather, relocalizing }} />
          : <Results {...{ t, lang, analysis, metrics, chat, question, setQuestion, ask, file,
            previewUrl, relocalizing, assistantEngine: health.data?.assistant,
            onStartNew: () => setView('dashboard') }} />}
      </main>

      <footer className="bottom">
        {t('app_name')} · v1.1.2 · build {BUILD_LABEL} · {t('footer_core')} · {t('footer_note')}
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------- dashboard */
function Dashboard({ t, form, setField, setForm, file, previewUrl, onPick, openPicker,
  fileRef, clearFile, info, uploadNote, previewBroken, setPreviewBroken,
  analyze, busy, sensors, history, device, setDevice, meta, metrics, samples }) {
  // Dashboard receives `t` (already language-bound); `lang` reaches it through `t`.

  const dropRef = useRef(null)
  const [over, setOver] = useState(false)
  const s = sensors.data
  const sampleList = samples?.samples || []

  return (
    <div className="grid">
      <div className="col">
        <Card title={t('upload_title')} step="1">
          <div
            ref={dropRef}
            className={`drop ${over ? 'over' : ''} ${file ? 'has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); onPick(e.dataTransfer.files?.[0]) }}
            onClick={file ? undefined : openPicker}
            onKeyDown={(e) => { if (!file && (e.key === 'Enter' || e.key === ' ')) openPicker() }}
            role={file ? undefined : 'button'}
            tabIndex={file ? undefined : 0}
          >
            {/*
              Visually hidden but NOT display:none - a display:none input silently
              refuses to open the picker in some browsers, which is exactly
              "clicking Choose photo does nothing". Both paths are wired: the native
              <label> and the programmatic openPicker().
            */}
            <input
              ref={fileRef}
              id="leaf-upload"
              className="sr-only"
              type="file"
              accept="image/*,.jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff,.heic,.heif"
              onChange={(e) => { onPick(e.target.files?.[0]); e.target.value = '' }}
            />
            {file ? (
              <div className="preview">
                {previewBroken ? (
                  <div className="preview-fallback">
                    <span style={{ fontSize: 26 }}>🖼️</span>
                    <span className="small">{t('preview_unavailable')}</span>
                  </div>
                ) : (
                  <img src={previewUrl} alt={t('alt_selected')} onError={() => setPreviewBroken(true)} />
                )}
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <b style={{ wordBreak: 'break-all' }}>{file.name}</b>
                  <p className="muted small" style={{ margin: '2px 0' }}>
                    {(file.size / 1024).toFixed(0)} KB · {file.type || 'image'}
                    {info?.w ? ` · ${info.w}x${info.h}${info.w2 ? ` -> ${info.w2}x${info.h2}` : ''}` : ''}
                  </p>
                  {uploadNote && (
                    <p className="small" style={{ color: '#1e7a37', margin: 0 }}>{uploadNote}</p>
                  )}
                  <div className="actions-bar">
                    <button type="button" className="ghost" disabled={busy}
                      onClick={(e) => { e.stopPropagation(); openPicker() }}>
                      {t('change_photo')}
                    </button>
                    <button type="button" className="ghost" disabled={busy}
                      onClick={(e) => { e.stopPropagation(); clearFile() }}>
                      {t('remove')}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div style={{ fontSize: 30 }}>📷</div>
                {/* a real <label> keeps the native path working even if scripted .click() is blocked */}
                <label htmlFor="leaf-upload" className="primary"
                  style={{ display: 'inline-block', cursor: 'pointer' }}
                  onClick={(e) => e.stopPropagation()}>
                  {t('choose_photo')}
                </label>
                <p className="muted small" style={{ marginTop: 8 }}>
                  {t('upload_hint')} ({t('accepted_types')}, ≤ {MAX_MB} MB) — {t('or_drag')}
                </p>
              </>
            )}
          </div>

          {/* explicit submit once a photo is ready — the step the flow was missing */}
          {file && (
            <div className="actions-bar" style={{ marginTop: 12 }}>
              <button className="primary" onClick={() => analyze()} disabled={busy}>
                {busy ? <><span className="spinner" /> {t('analyzing')}</> : t('analyze_photo')}
              </button>
              <span className="small muted">
                {busy ? t('upload_sending') : t('photo_ready')}
              </span>
            </div>
          )}

          {sampleList.length > 0 && (
            <Fold label={`${t('try_sample')} (${sampleList.length})`}>
              <SamplePicker t={t} samples={samples} busy={busy} onRun={(id) => analyze({ sampleId: id })} />
            </Fold>
          )}
        </Card>

        <Card title={t('field_title')} step="2">
          <div className="row three">
            <label className="field"><span>{t('soil_moisture')}</span>
              <input type="number" min="0" max="100" value={form.soil_moisture_pct}
                onChange={setField('soil_moisture_pct')} /></label>
            <label className="field"><span>{t('soil_ph')}</span>
              <input type="number" min="0" max="14" step="0.1" value={form.soil_ph}
                onChange={setField('soil_ph')} /></label>
            <label className="field"><span>{t('planted_crop')}</span>
              <select value={form.planted_crop} onChange={setField('planted_crop')}>
                {['tomato', 'potato', 'corn', 'apple', 'grape', 'bell_pepper'].map((c) => (
                  <option key={c} value={c}>{t(`crop_${c}`)}</option>
                ))}
              </select></label>
          </div>
          <div className="row">
            <label className="field"><span>{t('city')}</span>
              <input value={form.city} onChange={setField('city')} placeholder="Ahmedabad" /></label>
            <label className="field"><span>{t('area')}</span>
              <input type="number" min="0" step="0.1" value={form.area_ha} onChange={setField('area_ha')} /></label>
          </div>

          {/* the six N-P-K + climate boxes only feed the crop-recommendation model and
              arrive pre-filled, so they stay folded until someone wants to edit them */}
          <Fold label={`${t('crop_advisory')} ${t('crop_inputs_suffix')} — ${t('optional')}`}>
            <div className="row three">
              {['N', 'P', 'K'].map((k) => (
                <label className="field" key={k}><span>{k} (kg/ha)</span>
                  <input type="number" value={form[k]} onChange={setField(k)} /></label>
              ))}
            </div>
            <div className="row three">
              {[['temperature', '°C'], ['humidity', '%'], ['rainfall', 'mm']].map(([k, u]) => (
                <label className="field" key={k}><span>{k} ({u})</span>
                  <input type="number" step="0.1" value={form[k]} onChange={setField(k)} /></label>
              ))}
            </div>
          </Fold>

          <div className="actions-bar">
            <button className={file ? 'ghost' : 'primary'} onClick={() => analyze()} disabled={busy}>
              {busy ? <><span className="spinner" /> {t('analyzing')}</> : t('analyze')}
            </button>
            <button className="ghost" onClick={() => setForm((f) => ({ ...f, ...SAMPLE }))}>{t('use_soil_card')}</button>
            <label className="check">
              <input type="checkbox" checked={form.use_sensors}
                onChange={(e) => setForm((f) => ({ ...f, use_sensors: e.target.checked }))} />
              {t('use_sensor_moisture')}
            </label>
          </div>
        </Card>
      </div>

      <div className="col">
        <SensorCard t={t} s={s} history={history.data} device={device} setDevice={setDevice} />
        <MetricsCard t={t} metrics={metrics.data} meta={meta.data} />
      </div>
    </div>
  )
}

function SamplePicker({ t, samples, busy, onRun }) {
  const list = samples?.samples || []
  if (!list.length) return null
  return (
    <div className="samples">
      {list.map((s) => (
        <button
          key={s.id}
          className="sample"
          disabled={busy}
          title={`${t('expected')}: ${s.true_class_label || s.true_class.replace(/_/g, ' ')}`}
          onClick={() => onRun(s.id)}
        >
          <img src={encodeURI(s.image_url)} alt={s.true_class_label || t('alt_sample')} loading="lazy" />
          <span className="sample-name">{s.true_class_label || s.true_class.replace(/_/g, ' ')}</span>
          <span className={`tag ${s.correct ? 'routine' : 'today'}`}>
            {s.correct ? t('sample_right') : t('sample_hard')}
          </span>
        </button>
      ))}
    </div>
  )
}

function SensorCard({ t, s, history, device, setDevice }) {
  const soils = history?.samples?.map((x) => x.soil_moisture_pct) || []
  const temps = history?.samples?.map((x) => x.temperature_c) || []
  return (
    <Card title={t('sensors')} aside={<span className="badge low">{t('sim_badge')}</span>}>
      <label className="field"><span>{t('node')}</span>
        <select value={device} onChange={(e) => setDevice(e.target.value)}>
          <option value="esp32-field-1">{t('dev_north_option')}</option>
          <option value="esp32-field-2">{t('dev_south_option')}</option>
          <option value="esp32-greenhouse">{t('dev_poly_option')}</option>
        </select>
      </label>
      {s ? (
        <>
          {/* the three readings that change a decision stay on the surface */}
          <div className="quick">
            <div><span>{t('soil_moisture_short')}</span><b>{num(s.soil_moisture_pct)}%</b></div>
            <div><span>{t('temperature')}</span><b>{num(s.temperature_c)} °C</b></div>
            <div><span>{t('humidity')}</span><b>{num(s.humidity_pct)}%</b></div>
          </div>
          <div className={`status-line ${s.needs_irrigation ? 'dry' : 'ok'}`}>
            <b>{s.status_label || s.status}</b> · {s.device_name || s.device_id}
          </div>
          <Fold label={t('details')}>
            <div className="kv"><span>{t('soil_ph_short')}</span><b>{num(s.soil_ph, 2)}</b></div>
            <div className="kv"><span>{t('battery_signal')}</span><b>{num(s.battery_pct)}% · {s.rssi_dbm} dBm</b></div>
            <div className="kv"><span>{t('next_sample')}</span><b>{s.next_sample_in_s}s</b></div>
            {soils.length > 1 && (
              <div style={{ marginTop: 10 }}>
                <div className="small muted">{t('trend_soil_2h')} ({history.summary.trend_label || history.summary.trend})</div>
                <Sparkline points={soils} min={0} max={100} label={t('trend_aria')} />
                <div className="small muted">{t('air_temperature')}</div>
                <Sparkline points={temps} color="#f0b429" label={t('air_temperature')} />
              </div>
            )}
            <p className="small muted" style={{ marginTop: 8 }}>{s.note}</p>
          </Fold>
        </>
      ) : <p className="muted">{t('sensors')}…</p>}
    </Card>
  )
}

function MetricsCard({ t, metrics, meta }) {
  const f = metrics?.field_test
  return (
    <Card title={t('metrics')}>
      {f ? (
        <>
          <div className="quick">
            <div><span>{t('mf1')}</span><b>{num(f.macro_f1, 3)}</b></div>
            <div><span>{t('accuracy')}</span><b>{num(f.accuracy, 3)}</b></div>
            <div><span>{t('top3_acc')}</span><b>{num(f.top3_accuracy, 3)}</b></div>
          </div>
          <Fold label={t('details')}>
            <table className="metrics">
              <tbody>
                <tr><td>{t('images_field')}</td><td>{f.n_images}</td></tr>
                <tr><td>{t('classes_scored')}</td><td>{f.n_classes_scored}</td></tr>
              </tbody>
            </table>
            <p className="small muted" style={{ marginTop: 8 }}>
              {t('metrics_note')} {meta?.datasets?.field_test}
            </p>
          </Fold>
        </>
      ) : <p className="muted small">{t('metrics_after')}</p>}
    </Card>
  )
}

/* --------------------------------------------------------------- results */
function Results({ t, analysis, chat, question, setQuestion, ask, previewUrl,
  relocalizing, assistantEngine, onStartNew }) {
  if (!analysis) {
    return (
      <section className="card empty">
        <h2>{t('results')}</h2>
        <p className="muted">{t('no_analysis')}</p>
        <button className="primary" onClick={() => onStartNew()}>{t('start_analysis')}</button>
      </section>
    )
  }
  const { prediction: p, risk, irrigation, weather, sustainability: sus, actions, recommendations,
    crop_recommendation: rec, warnings, narrative } = analysis

  const riskColor = { low: '#2e8b45', moderate: '#f0b429', high: '#e07b00', critical: '#d64545' }[risk?.risk] || '#6b7f70'

  return (
    <div className="results">
      {relocalizing && <Alert kind="info">{t('relocalizing')}</Alert>}

      {/* the whole advisory in one box: what it is, how sure, and the four numbers
          that decide what the farmer does next */}
      <section className="card verdict">
        {previewUrl && <img className="shot" src={previewUrl} alt={t('alt_analyzed')} />}
        <div className="verdict-body">
          <div className="eyebrow">{t('at_a_glance')}</div>
          <h2 className="headline">{p ? (p.condition_localized || p.condition) : t('no_photo_note')}</h2>
          {p && (
            <p className="muted small tight">
              {p.crop_localized || p.crop} · {t('confidence')} {pct(p.confidence)}
            </p>
          )}
          {narrative && <p className="verdict-text">{narrative}</p>}
          <div className="stats">
            {risk && <Stat label={t('risk')} value={risk.risk_label || risk.risk} tone={risk.risk} />}
            {irrigation && <Stat label={t('irrigation')} value={irrigation.action_label || irrigation.action} />}
            {sus && <Stat label={t('sustainability')} value={`${Math.round(sus.total)} · ${sus.grade}`} />}
            {weather && (
              <Stat label={t('weather')}
                value={weather.ok ? `${num(weather.temperature_c)} °C · ${weather.condition}` : t('offline')} />
            )}
          </div>
        </div>
      </section>

      {warnings?.length > 0 && (
        <div className="alerts">{warnings.map((w, i) => <Alert key={i}>{w}</Alert>)}</div>
      )}

      <div className="grid">
        <Card title={t('prediction')} aside={p ? <span className="badge low">{pct(p.confidence)}</span> : null}>
          {p ? (
            <>
              <div className="bars">
                {p.top3.map((r) => (
                  <div className="bar" key={r.class}>
                    <span>{r.condition_localized || r.condition}{' '}
                      <span className="muted small">({r.crop_localized || r.crop})</span></span>
                    <b>{pct(r.confidence)}</b>
                    <div className="track"><div className="fill" style={{ width: `${r.confidence * 100}%` }} /></div>
                  </div>
                ))}
              </div>
              <Fold label={t('details')}>
                <div className="kv"><span>{t('confidence')}</span><b>{pct(p.confidence)}</b></div>
                <div className="kv"><span>{t('engine')}</span><b>{p.model_name} @{p.img_size}px</b></div>
                <div className="kv"><span>{t('inference_time')}</span><b>{p.inference_ms} ms</b></div>
              </Fold>
            </>
          ) : <p className="muted">{t('no_photo_note')}</p>}
        </Card>

        {irrigation && (
          <Card title={t('irrigation')} aside={<span className="badge moderate">{irrigation.action_label || irrigation.action.replace('_', ' ')}</span>}>
            <div className="kv"><span>{t('soil_moisture_short')}</span><b>{num(irrigation.soil_moisture_pct)}%</b></div>
            <div className="kv"><span>{t('rain_probability')}</span><b>{num(irrigation.rain_probability_pct, 0)}%</b></div>
            <div className="kv"><span>{t('water_stress')}</span><b>{irrigation.water_stress_label || irrigation.water_stress}</b></div>
            {irrigation.et0_proxy_mm_day ? <div className="kv"><span>{t('et0_proxy')}</span><b>{num(irrigation.et0_proxy_mm_day, 2)} mm/day</b></div> : null}
            <Fold label={`${t('why')} · ${t('details')}`}>
              <ul className="bullets">{irrigation.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </Fold>
            {irrigation.alerts?.length > 0 && (
              <div className="alerts">{irrigation.alerts.map((a, i) => <Alert key={i}>{a}</Alert>)}</div>
            )}
          </Card>
        )}

        {actions?.length > 0 && (
          <Card title={t('actions')}>
            <ul className="actions">
              {actions.map((a, i) => (
                <li key={i}>
                  <span className={`tag ${a.priority}`}>{a.priority_label || a.priority}</span>
                  <span>{a.text} <span className="muted small">· {a.kind_label || a.kind}</span></span>
                </li>
              ))}
            </ul>
            {recommendations?.chemical_option && (
              <Fold label={t('chemical_option')}>
                <p className="small muted" style={{ marginTop: 4 }}>
                  <b>{recommendations.chemical_option.product}</b> — {recommendations.chemical_option.dose}. {recommendations.chemical_option.note}
                </p>
              </Fold>
            )}
          </Card>
        )}

        {weather && (
          <Card title={t('weather')} aside={<span className={`badge ${weather.ok ? 'low' : 'moderate'}`}>{weather.ok ? t('live') : t('offline')}</span>}>
            {weather.ok ? (
              <>
                <div className="big" style={{ fontSize: 22 }}>{num(weather.temperature_c)} °C · {weather.condition}</div>
                <div className="kv"><span>{weather.city}{weather.country ? `, ${weather.country}` : ''}</span><b>{weather.source}</b></div>
                <div className="kv"><span>{t('humidity')}</span><b>{num(weather.humidity_pct, 0)}%</b></div>
                <div className="kv"><span>{t('wind')}</span><b>{num(weather.wind_kph)} km/h</b></div>
                <div className="kv"><span>{t('rain_today_week')}</span><b>{num(weather.rain_today_mm)} / {num(weather.weekly_rain_mm)} mm</b></div>
                {weather.daily?.length > 0 && (
                  <Fold label={t('forecast_4day')}>
                    <table className="metrics">
                      <tbody>
                        {weather.daily.slice(0, 4).map((d) => (
                          <tr key={d.date}>
                            <td>{d.date}</td>
                            <td>{num(d.t_min, 0)}–{num(d.t_max, 0)} °C</td>
                            <td>{num(d.rain_probability, 0)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Fold>
                )}
              </>
            ) : (
              <Alert kind="info">{weather.note || t('weather_unavailable')}</Alert>
            )}
          </Card>
        )}

        {risk && (
          <Card title={`${t('risk')} · ${risk.crop}`} aside={<span className={`badge ${risk.risk}`}>{risk.risk_label}</span>}>
            <div className="kv"><span>{t('condition')}</span><b>{risk.condition_localized || risk.condition}</b></div>
            <div className="kv"><span>{t('confidence_band')}</span><b>{risk.confidence_band_label || risk.confidence_band}</b></div>
            <div className="kv"><span>{t('advisory_level')}</span><b>{risk.advisory_level_label || risk.advisory_level}</b></div>
            <div className="kv"><span>{t('kb_severity')}</span><b>{risk.severity_label || risk.severity_kb}</b></div>
            <Fold label={`${t('findings')} · ${(risk.notes?.length || 0) + (risk.symptoms?.length || 0)}`}>
              {risk.notes?.length > 0 && (
                <>
                  <h3>{t('reasons')}</h3>
                  <ul className="bullets">{risk.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                </>
              )}
              {risk.symptoms?.length > 0 && (
                <>
                  <h3>{t('what_to_look_for')}</h3>
                  <ul className="bullets">{risk.symptoms.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </>
              )}
            </Fold>
          </Card>
        )}

        {sus && (
          <Card title={t('sustainability')} aside={<span className="badge low">{sus.band_label || sus.band}</span>}>
            <div className="gauge">
              <Donut value={sus.total} grade={sus.grade} color={riskColor}
                label={t('donut_aria', { v: Math.round(sus.total) })} gradeWord={t('grade')} />
              <div className="legend">
                <div className="kv"><span>{t('weakest')}</span><b>{sus.weakest_area_label || sus.weakest_area}</b></div>
              </div>
            </div>
            <Alert kind="info">{sus.top_tip}</Alert>
            <Fold label={t('subscore_breakdown')}>
              <div className="legend">
                {Object.entries(sus.subscores).map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 4 }}>
                    <div className="bar">
                      <span>{sus.subscore_labels?.[k] || k} <span className="muted small">w {sus.weights[k]}</span></span>
                      <b>{num(v)}</b>
                      <div className="track"><div className="fill" style={{ width: `${v}%` }} /></div>
                    </div>
                  </div>
                ))}
              </div>
              <p className="small muted" style={{ marginTop: 8 }}>{sus.formula}</p>
            </Fold>
          </Card>
        )}

        {rec && (
          <Card title={t('crop_advisory')} aside={<span className="badge low">{rec.top_crop_localized || rec.top_crop}</span>}>
            <div className="bars">
              {rec.recommendations.map((r) => (
                <div className="bar" key={r.crop}>
                  <span>{r.crop_localized || r.crop}</span><b>{pct(r.probability)}</b>
                  <div className="track"><div className="fill" style={{ width: `${r.probability * 100}%` }} /></div>
                </div>
              ))}
            </div>
            <Fold label={`${t('why')} · ${t('details')}`}>
              <p className="small muted" style={{ marginTop: 4 }}>{rec.advice}</p>
              <p className="small muted">{t('engine')}: {rec.engine}</p>
            </Fold>
          </Card>
        )}

        <AssistantChat {...{ t, chat, question, setQuestion, ask, engine: assistantEngine }} />
      </div>
    </div>
  )
}

function AssistantChat({ t, chat, question, setQuestion, ask, engine }) {
  // The badge tells the truth about which engine answered: the deterministic
  // grounded rules, or those rules rephrased by an LLM (Groq by default).
  const llm = engine?.llm_enabled ? engine.provider : null
  const ref = useRef(null)
  useEffect(() => {
    // Guarded: a host without Element.scrollTo would otherwise throw inside an
    // effect, which unmounts the whole tree and shows a blank page.
    try { ref.current?.scrollTo({ top: ref.current.scrollHeight }) } catch { /* ignore */ }
  }, [chat])
  // Labels are shown in the UI language and sent as-is: the assistant understands
  // native-script questions and always answers in the language it is asked in.
  const chips = ['chip_disease', 'chip_irrigate', 'chip_rain', 'chip_crop', 'chip_prevent']
    .map((k) => t(k))
  return (
    <Card title={t('assistant')}
      aside={<span className="badge low" title={llm ? t('engine_tip_llm', { p: llm })
                                                   : t('engine_tip_grounded')}>
        {llm ? t('badge_llm', { p: llm }) : t('badge_grounded')}
      </span>}>
      <div className="chat" ref={ref}>
        {chat.length === 0 && <p className="muted small">{t('chat_intro')}</p>}
        {chat.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}
            {m.sources?.length > 0 && <span className="src">{t('source')}: {m.sources.join(' · ')}</span>}
          </div>
        ))}
      </div>
      <div className="chips">
        {chips.map((c) => <button key={c} onClick={() => ask(c)}>{c}</button>)}
      </div>
      <div className="chat-input">
        <input value={question} placeholder={t('ask_placeholder')}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask()} />
        <button className="primary" onClick={() => ask()}>{t('send')}</button>
      </div>
    </Card>
  )
}
