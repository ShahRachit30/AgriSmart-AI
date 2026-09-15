#!/usr/bin/env python3
"""Re-apply the farmer UI pass to App.jsx.

The workspace snapshot reverted the frontend to the pre-farmer-pass version, so the
same patches are re-applied here in one reviewable place. Run from the repo root:

    python scripts/apply_farmer_pass.py

Every anchor is asserted, so a partial/moved file fails loudly instead of silently
producing a half-patched UI.
"""
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app" / "frontend" / "src" / "App.jsx"
s = APP.read_text()
done = []


def patch(old: str, new: str, label: str) -> None:
    global s
    assert s.count(old) == 1, f"anchor for {label!r} matched {s.count(old)} times"
    s = s.replace(old, new)
    done.append(label)


# ---------------------------------------------------------------- constants
patch(
    """const num = (v, digits = 1) =>""",
    """// The 38-class model covers these crops. Kept in one place so the picker, the icons
// and the tests agree with `modules/recommendations.py::CROPS`.
const CROPS = ['tomato', 'potato', 'corn', 'bell_pepper', 'apple', 'grape', 'orange',
  'peach', 'cherry', 'strawberry', 'blueberry', 'raspberry', 'squash', 'soybean']
const CROP_ICON = {
  tomato: '🍅', potato: '🥔', corn: '🌽', bell_pepper: '🫑', apple: '🍎', grape: '🍇',
  orange: '🍊', peach: '🍑', cherry: '🍒', strawberry: '🍓', blueberry: '🫐',
  raspberry: '🫐', squash: '🎃', soybean: '🌱',
}
const CROP_COUNT = CROPS.length
const DISEASE_COUNT = 38
// Speech synthesis voice per language (falls back to the default voice).
const SPEECH_LANG = { en: 'en-IN', hi: 'hi-IN', gu: 'gu-IN' }
const stamp = () => {
  const d = new Date(), p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}

const num = (v, digits = 1) =>""",
    "crop constants",
)

# ------------------------------------------------------- LiveCapture/Listen
patch(
    """/* ------------------------------------------------------------- dashboard */""",
    """/* -------------------------------------------------- farmer helpers */
/**
 * Read the verdict out loud. Many farmers use the app in the field, with dirty or
 * gloved hands, and some read Gujarati/Hindi more easily when they hear it. Falls
 * back silently to nothing when the browser has no voice for that language - it is
 * a convenience, never the only way to get the information.
 */
function ListenButton({ t, lang, text }) {
  const [speaking, setSpeaking] = useState(false)
  const supported = typeof window !== 'undefined' && !!window.speechSynthesis
  const say = () => {
    if (!supported || !text) return
    try {
      window.speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = SPEECH_LANG[lang] || 'en-IN'
      u.rate = 0.92
      u.onend = () => setSpeaking(false)
      u.onerror = () => setSpeaking(false)
      setSpeaking(true)
      window.speechSynthesis.speak(u)
    } catch { setSpeaking(false) }
  }
  if (!supported) return <p className="muted small tight">{t('listen_unsupported')}</p>
  return (
    <button type="button" className="ghost" onClick={say}>
      {speaking ? `🔊 ${t('listen_stop')}` : `🔊 ${t('listen')}`}
    </button>
  )
}

/**
 * Live camera capture: a farmer points the phone at the leaf and taps the shutter,
 * instead of photographing it, leaving the browser, and picking the file again.
 *
 * The frame is drawn to a canvas and handed to the SAME two-step upload flow as a
 * picked file, so nothing about the review step changes. Every failure path
 * (permission denied, no camera, no browser support) explains itself and offers the
 * phone's native camera plus the ordinary file picker - never a dead end.
 */
function LiveCapture({ t, onCapture, onClose, onUsePhone, onChooseFile }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [facing, setFacing] = useState('environment')
  const [error, setError] = useState(null)

  const stop = useCallback(() => {
    const stream = streamRef.current
    if (stream) stream.getTracks().forEach((tr) => { try { tr.stop() } catch { /* ignore */ } })
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const start = useCallback(async (mode) => {
    setError(null)
    setReady(false)
    stop()
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported')
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: mode, width: { ideal: 1280 } }, audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => { /* autoplay may need the tap */ })
      }
      setReady(true)
    } catch (e) {
      const name = e?.name || ''
      setError(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied'
        : name === 'NotFoundError' || name === 'OverconstrainedError' ? 'unavailable'
          : 'failed')
    }
  }, [stop])

  useEffect(() => { start(facing); return stop }, [start, facing, stop])

  // Esc closes the panel; the stream must never outlive the panel.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const shoot = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      if (!blob) return
      stop()
      onCapture(new File([blob], `camera_${stamp()}.jpg`, { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.92)
  }

  if (error) {
    return (
      <div className="capture">
        <div className="capture-error">
          <span style={{ fontSize: 30 }} aria-hidden>📷</span>
          <b>{t(error === 'denied' ? 'capture_denied' : error === 'unavailable' ? 'capture_unavailable' : 'capture_failed')}</b>
          <p className="muted small">{t('capture_escape_hint')}</p>
          <div className="actions-bar">
            <button type="button" className="primary" onClick={onUsePhone}>{t('capture_use_phone')}</button>
            <button type="button" className="ghost" onClick={onChooseFile}>{t('capture_choose_instead')}</button>
            <button type="button" className="ghost" onClick={onClose}>{t('capture_close')}</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="capture">
      <video ref={videoRef} className="capture-video" playsInline muted autoPlay />
      {!ready && <div className="capture-wait"><span className="spinner" /> {t('capture_starting')}</div>}
      <div className="capture-bar">
        <button type="button" className="ghost" onClick={onClose}>{t('capture_close')}</button>
        <button type="button" className="shutter" onClick={shoot} disabled={!ready}
          aria-label={t('capture_shoot')} title={t('capture_shoot')} />
        <button type="button" className="ghost"
          onClick={() => setFacing((f) => (f === 'environment' ? 'user' : 'environment'))}>
          {t('capture_switch')}
        </button>
      </div>
      <p className="capture-tip">{t('capture_tip')}</p>
    </div>
  )
}

/* ------------------------------------------------------------- dashboard */""",
    "LiveCapture + ListenButton",
)

# ------------------------------------------------------------ app state
patch(
    """  const [chat, setChat] = useState([])
  const [question, setQuestion] = useState('')""",
    """  const [chat, setChat] = useState([])
  const [question, setQuestion] = useState('')
  const [camera, setCamera] = useState(false)     // live capture panel open?
  const [notice, setNotice] = useState(null)      // honest refusal card (not an error)
  const phoneCamRef = useRef(null)                // hidden capture="environment" input""",
    "app state",
)

# --------------------------------------------------------- camera handlers
patch(
    """  const modelOk = health.data?.model_available""",
    """  /* -------------------------------------------------- photo capture paths
     Three ways to get a leaf photo in, in order of preference for a farmer:
       1. live capture in the app (getUserMedia) when the browser allows it,
       2. the phone's native camera app (a hidden capture="environment" input),
       3. a file from the gallery / disk (the picker that was always there).
     Only (1) can fail, and when it does the other two are offered immediately. */
  const onCapture = useCallback((captured) => {
    setCamera(false)
    setNotice(null)
    onPick(captured)
  }, [onPick])

  const openPhoneCamera = useCallback(() => {
    setCamera(false)
    const el = phoneCamRef.current
    if (el) { el.value = ''; el.click() }
  }, [])

  const openCamera = useCallback(async () => {
    // no mediaDevices (http on LAN, older browser) -> go straight to the native app
    if (!navigator.mediaDevices?.getUserMedia) { openPhoneCamera(); return }
    setNotice(null)
    setCamera(true)
  }, [openPhoneCamera])

  const closeCamera = useCallback(() => setCamera(false), [])

  const modelOk = health.data?.model_available""",
    "camera handlers",
)

# --------------------------------------------- shutter: tolerate 0x0 video
patch(
    """  const shoot = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight""",
    """  const shoot = () => {
    const video = videoRef.current
    if (!video) return
    // some browsers report 0x0 until the first frame lands - fall back to a sane
    // frame size rather than refusing to take the photo
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 1280
    canvas.height = video.videoHeight || 720""",
    "shutter tolerates a 0x0 video",
)

# ------------------------------------------------------ refusal handling
patch(
    """      if (res.ok === false) {
        const msg = res.message || 'Analysis failed'
        setError(res.hint ? `${msg} — ${res.hint}` : msg)
        scrollTop()   // make the banner visible
      }""",
    """      if (res.ok === false) {
        const msg = res.message || 'Analysis failed'
        if (res.error === 'not_a_leaf') {
          // Not an error - the app is telling the farmer it cannot help with this
          // photo. Say so kindly, explain, and offer to take another one.
          setNotice({ message: msg, hint: res.hint })
          setError(null)
        } else {
          setNotice(null)
          setError(res.hint ? `${msg} — ${res.hint}` : msg)
        }
        scrollTop()   // make the card visible
      }""",
    "refusal handling",
)

# ------------------------------------------------------------ header
patch(
    """        <div className=\"brand\">
          <div className=\"logo\" aria-hidden>🌿</div>
          <div>
            <h1>{t('app_name')}</h1>
            <p>{t('tagline')}</p>
          </div>
        </div>""",
    """        <div className=\"brand\">
          <div className=\"logo\" aria-hidden>🌿</div>
          <div>
            <h1>{t('app_name')}</h1>
            <p>{t('tagline')}</p>
            <p className=\"coverage\">{t('coverage', { d: DISEASE_COUNT, c: CROP_COUNT })}</p>
          </div>
        </div>""",
    "header coverage",
)

patch(
    """        <div className=\"lang\">
          {LANGS.map((l) => (
            <button key={l} className={l === lang ? 'active' : ''} onClick={() => changeLang(l)}
              title={t('switch_note')} aria-pressed={l === lang}>
              {LANG_LABEL[l]}
            </button>
          ))}
        </div>""",
    """        <div className=\"lang\" role=\"group\" aria-label={t('language')} title={t('choose_language')}>
          {LANGS.map((l) => (
            <button key={l} className={`lang-btn ${l === lang ? 'active' : ''}`} lang={l}
              onClick={() => changeLang(l)}
              title={t('switch_note')} aria-pressed={l === lang}>
              {LANG_LABEL[l]}
            </button>
          ))}
        </div>""",
    "language buttons",
)

# ------------------------------------------------------------ props + footer
patch(
    """          ? <Dashboard {...{ t, lang, form, setField, setForm, file, previewUrl, onPick, openPicker,
            fileRef, clearFile, info, uploadNote, previewBroken, setPreviewBroken,
            analyze, busy, sensors, history, device, setDevice, meta, metrics, samples: samples.data,
            weather: analysis?.weather, relocalizing }} />""",
    """          ? <Dashboard {...{ t, lang, form, setField, setForm, file, previewUrl, onPick, openPicker,
            fileRef, clearFile, info, uploadNote, previewBroken, setPreviewBroken, camera,
            notice, onCloseCamera: closeCamera, phoneCamRef, openPhoneCamera, openCamera,
            onCapture, analyze, busy, sensors, history, device, setDevice, meta, metrics,
            samples: samples.data, weather: analysis?.weather, relocalizing }} />""",
    "dashboard props",
)

patch(
    """        {t('app_name')} · v1.1.2 · build {BUILD_LABEL} · {t('footer_core')} · {t('footer_note')}""",
    """        {t('app_name')} · v{health.data?.version || '1.2.0'} · build {BUILD_LABEL} · {t('footer_core')} · {t('footer_note')}""",
    "footer version",
)

# ------------------------------------------------------- dashboard wiring
patch(
    """function Dashboard({ t, form, setField, setForm, file, previewUrl, onPick, openPicker,
  fileRef, clearFile, info, uploadNote, previewBroken, setPreviewBroken,
  analyze, busy, sensors, history, device, setDevice, meta, metrics, samples }) {""",
    """function Dashboard({ t, lang, form, setField, setForm, file, previewUrl, onPick, openPicker,
  fileRef, clearFile, info, uploadNote, previewBroken, setPreviewBroken, camera, notice,
  onCloseCamera, phoneCamRef, openPhoneCamera, openCamera, onCapture,
  analyze, busy, sensors, history, device, setDevice, meta, metrics, samples }) {""",
    "dashboard signature",
)

# ----------------------------------------------- upload card: refusal + capture
patch(
    """        <Card title={t('upload_title')} step=\"1\">
          <div
            ref={dropRef}""",
    """        <Card title={t('upload_title')} step=\"1\">
          {/* The app refuses photos that are not leaves. That is good news for the
              farmer, so it reads as advice with a way forward - not a red error. */}
          {notice && (
            <div className=\"card notice\" role=\"status\">
              <div className=\"notice-head\">
                <span style={{ fontSize: 30 }} aria-hidden>🌿</span>
                <div>
                  <b>{notice.message}</b>
                  {notice.hint && <p className=\"muted small tight\">{notice.hint}</p>}
                </div>
              </div>
              <div className=\"actions-bar\">
                <button type=\"button\" className=\"primary\" onClick={openCamera}>
                  📸 {t('capture_take')}
                </button>
                <button type=\"button\" className=\"ghost\" onClick={openPicker}>
                  {t('pick_another')}
                </button>
              </div>
            </div>
          )}

          {camera && (
            <LiveCapture t={t} onCapture={onCapture} onClose={onCloseCamera}
              onUsePhone={openPhoneCamera} onChooseFile={openPicker} />
          )}

          <div
            ref={dropRef}""",
    "notice + capture panel",
)

patch(
    """              <>
                <div style={{ fontSize: 30 }}>📷</div>
                {/* a real <label> keeps the native path working even if scripted .click() is blocked */}
                <label htmlFor=\"leaf-upload\" className=\"primary\"
                  style={{ display: 'inline-block', cursor: 'pointer' }}
                  onClick={(e) => e.stopPropagation()}>
                  {t('choose_photo')}
                </label>
                <p className=\"muted small\" style={{ marginTop: 8 }}>
                  {t('upload_hint')} ({t('accepted_types')}, ≤ {MAX_MB} MB) — {t('or_drag')}
                </p>
              </>""",
    """              <>
                <div style={{ fontSize: 34 }} aria-hidden>🖼️</div>
                <p className=\"lead\">{t('which_photo')}</p>
                {/* a real <label> keeps the native path working even if scripted .click() is blocked */}
                <label htmlFor=\"leaf-upload\" className=\"primary big\"
                  style={{ display: 'inline-block', cursor: 'pointer' }}
                  onClick={(e) => e.stopPropagation()}>
                  🖼️ {t('choose_photo')}
                </label>
                <button type=\"button\" className=\"ghost big\" onClick={openCamera}>
                  📸 {t('capture_take')}
                </button>
                {/* the phone's own camera app - works on every phone browser, even
                    when getUserMedia is unavailable (http, older Android) */}
                <input ref={phoneCamRef} id=\"leaf-camera\" className=\"sr-only\" type=\"file\"
                  accept=\"image/*\" capture=\"environment\"
                  onChange={(e) => { onPick(e.target.files?.[0]); e.target.value = '' }} />
                <p className=\"muted small\" style={{ marginTop: 8 }}>
                  {t('upload_hint')} ({t('accepted_types')}, ≤ {MAX_MB} MB) — {t('or_drag')}
                </p>
              </>""",
    "empty-state camera buttons",
)

# --------------------------------------------------------- crop chips + select
patch(
    """        <Card title={t('field_title')} step=\"2\">
          <div className=\"row three\">""",
    """        <Card title={t('field_title')} step=\"2\">
          {/* Plain-language crop picker: a farmer recognises the picture and the word
              in their own language faster than a dropdown. */}
          <p className=\"field-label\">{t('planted_crop')}</p>
          <div className=\"chips crops\" role=\"group\" aria-label={t('planted_crop')}>
            {CROPS.map((c) => (
              <button key={c} type=\"button\" className={`chip crop ${form.planted_crop === c ? 'on' : ''}`}
                aria-pressed={form.planted_crop === c}
                onClick={() => setForm((f) => ({ ...f, planted_crop: c }))}>
                <span aria-hidden>{CROP_ICON[c]}</span> {t(`crop_${c}`)}
              </button>
            ))}
          </div>

          <div className=\"row three\">""",
    "crop chips",
)

patch(
    """            <label className=\"field\"><span>{t('planted_crop')}</span>
              <select value={form.planted_crop} onChange={setField('planted_crop')}>
                {['tomato', 'potato', 'corn', 'apple', 'grape', 'bell_pepper'].map((c) => (
                  <option key={c} value={c}>{t(`crop_${c}`)}</option>
                ))}
              </select></label>""",
    """            <label className=\"field\"><span>{t('planted_crop')}</span>
              <select value={form.planted_crop} onChange={setField('planted_crop')}>
                {CROPS.map((c) => (
                  <option key={c} value={c}>{t(`crop_${c}`)}</option>
                ))}
              </select></label>""",
    "crop select from CROPS",
)

APP.write_text(s)
print(f"applied {len(done)} patches:")
for label in done:
    print(f"  - {label}")
