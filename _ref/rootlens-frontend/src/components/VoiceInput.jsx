import { useEffect, useRef, useState } from 'react';
import { Check, LoaderCircle, Mic, X } from 'lucide-react';
import { postForm } from '../lib/api';

// Speak to the assistant. The browser records the mic; the API turns it into text with Whisper (English, Hindi,
// Kannada), then the words are asked like a typed question. Works in every browser that can record audio,
// not only the ones with built-in speech recognition. The audio is not stored.
const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
];
const BARS = 28;

const pickType = () => ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find((t) => window.MediaRecorder?.isTypeSupported?.(t)) ?? '';

export const VoiceInput = ({ disabled, onText }) => {
  const [state, setState] = useState('idle'); // idle | recording | sending
  const [lang, setLang] = useState('en');
  const [error, setError] = useState(null);
  const rec = useRef(null);
  const chunks = useRef([]);
  const cancelled = useRef(false);
  const bars = useRef(null);
  const raf = useRef(0);
  const audio = useRef(null);
  const supported = typeof window !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && !!window.MediaRecorder;

  const stopMeter = () => {
    cancelAnimationFrame(raf.current);
    audio.current?.ctx.close().catch(() => {});
    audio.current?.stream.getTracks().forEach((t) => t.stop());
    audio.current = null;
  };
  useEffect(() => stopMeter, []);

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = pickType();
      const r = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      chunks.current = [];
      cancelled.current = false;
      r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      r.onstop = async () => {
        stopMeter();
        if (cancelled.current || !chunks.current.length) return setState('idle');
        setState('sending');
        const blob = new Blob(chunks.current, { type: r.mimeType || 'audio/webm' });
        const form = new FormData();
        form.append('file', blob, blob.type.includes('mp4') ? 'speech.mp4' : blob.type.includes('ogg') ? 'speech.ogg' : 'speech.webm');
        form.append('language', lang);
        try {
          const res = await postForm('/api/ai/transcribe', form);
          if (res.text) onText(res.text);
          else setError("Didn't catch that. Try again.");
        } catch (e) {
          setError(e?.message || 'Speech could not be read');
        }
        setState('idle');
      };
      // live level meter: an analyser drives the bars directly (no React re-render per frame)
      const ctx = new AudioContext();
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(an);
      audio.current = { ctx, stream };
      const buf = new Uint8Array(an.fftSize);
      const levels = new Array(BARS).fill(0.06);
      let last = 0;
      const tick = (now) => {
        an.getByteTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += ((v - 128) / 128) ** 2;
        const rms = Math.min(1, Math.sqrt(sum / buf.length) * 4);
        if (now - last > 50) {
          levels.shift();
          levels.push(Math.max(0.06, rms));
          last = now;
        }
        bars.current?.querySelectorAll('i').forEach((el, i) => {
          el.style.transform = `scaleY(${levels[i]})`;
        });
        raf.current = requestAnimationFrame(tick);
      };
      raf.current = requestAnimationFrame(tick);
      rec.current = r;
      r.start();
      setState('recording');
    } catch (e) {
      stopMeter();
      setError(e?.name === 'NotAllowedError' ? 'Microphone access is off for this site.' : 'No microphone found.');
      setState('idle');
    }
  };

  const finish = () => rec.current?.state === 'recording' && rec.current.stop();
  const cancel = () => {
    cancelled.current = true;
    finish();
  };

  if (!supported) return null;

  if (state === 'idle' || state === 'sending')
    return (
      <>
        <button type="button" onClick={start} disabled={disabled || state === 'sending'} className="btn-ghost shrink-0" aria-label="Speak your question"
          title={error ?? 'Speak in English, Hindi or Kannada'}>
          {state === 'sending' ? <LoaderCircle size={16} className="animate-spin" /> : <Mic size={16} />}
        </button>
        {error && <span role="status" className="sr-only">{error}</span>}
      </>
    );

  return (
    <div className="absolute inset-0 z-10 flex items-center gap-2 rounded-2xl bg-panel/95 px-2 backdrop-blur" role="group" aria-label="Recording your question">
      <button type="button" onClick={cancel} className="grid size-10 shrink-0 place-items-center rounded-full bg-ink/10 hover:bg-ink/15" aria-label="Cancel">
        <X size={18} />
      </button>
      <div ref={bars} className="flex h-9 min-w-0 flex-1 items-center justify-center gap-[3px]" aria-hidden="true">
        {Array.from({ length: BARS }, (_, i) => (
          <i key={i} className="block h-full w-[3px] origin-center rounded-full bg-accent/80" style={{ transform: 'scaleY(0.06)', transition: 'transform 60ms linear' }} />
        ))}
      </div>
      <div className="hidden shrink-0 gap-1 sm:flex">
        {LANGS.map((l) => (
          <button key={l.code} type="button" onClick={() => setLang(l.code)} aria-pressed={lang === l.code}
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${lang === l.code ? 'bg-ink text-panel' : 'bg-ink/10 text-ink/70'}`}>
            {l.label}
          </button>
        ))}
      </div>
      <button type="button" onClick={finish} className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-white hover:brightness-110" aria-label="Send what I said">
        <Check size={18} />
      </button>
    </div>
  );
};
