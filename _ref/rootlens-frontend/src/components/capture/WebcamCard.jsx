import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, LoaderCircle, RefreshCw, Video } from 'lucide-react';
import { CardTitle } from '../ui';

const explain = (e) => {
  if (e?.name === 'NotAllowedError' || e?.name === 'SecurityError') return 'Camera access was blocked. Allow the camera for this site in the browser address bar, then try again, or upload a photo instead.';
  if (e?.name === 'NotFoundError' || e?.name === 'OverconstrainedError') return 'No camera was found on this device. Upload a photo instead.';
  if (e?.name === 'NotReadableError' || e?.name === 'AbortError') return 'The camera is busy or not available. Close other apps that use it and try again.';
  return e?.message || 'The camera could not be started.';
};

// Live webcam preview, one still per capture. The stream is stopped as soon as a frame is taken and when the card unmounts,
// so the camera light never stays on behind another page.
const WebcamCard = ({ onCapture, busy }) => {
  const video = useRef(null);
  const stream = useRef(null);
  const alive = useRef(true);
  const [state, setState] = useState('idle'); // idle | starting | live | captured | error
  const [error, setError] = useState('');
  const [still, setStill] = useState(null);

  const stop = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
  }, []);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      stop();
    };
  }, [stop]);

  useEffect(() => () => still && URL.revokeObjectURL(still), [still]);

  const start = async () => {
    setError('');
    setStill(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser cannot open a camera here (it needs https or localhost). Upload a photo instead.');
      setState('error');
      return;
    }
    setState('starting');
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1920 }, height: { ideal: 1080 } } });
      if (!alive.current) {
        s.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = s;
      video.current.srcObject = s;
      await video.current.play().catch(() => {});
      setState('live');
    } catch (e) {
      if (!alive.current) return;
      setError(explain(e));
      setState('error');
    }
  };

  const capture = () => {
    const v = video.current;
    if (!v || !v.videoWidth) {
      setError('The camera is not ready yet. Wait a moment and try again.');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext('2d').drawImage(v, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setError('Could not take a picture from the camera.');
          return;
        }
        stop();
        setStill(URL.createObjectURL(blob));
        setState('captured');
        onCapture(blob);
      },
      'image/jpeg',
      0.92,
    );
  };

  return (
    <section className="card">
      <CardTitle sub="Hold the run sheet or machine screen to the camera, fill the frame and keep it still. The vision model reads numbers only.">Capture from webcam</CardTitle>
      <div className="relative grid aspect-video place-items-center overflow-hidden rounded-2xl bg-ink/90 text-white/70">
        <video ref={video} playsInline muted autoPlay className={`absolute inset-0 size-full object-cover ${state === 'live' ? '' : 'hidden'}`} aria-label="Live camera preview" />
        {state === 'captured' && still && <img src={still} alt="Frame taken from the webcam" className="absolute inset-0 size-full object-cover" />}
        {state === 'idle' && (
          <div className="flex flex-col items-center gap-2 px-4 text-center text-sm">
            <Video size={26} />
            <span>The camera starts when you press the button.</span>
          </div>
        )}
        {state === 'starting' && (
          <div role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" /> Waiting for the camera...</div>
        )}
        {state === 'error' && (
          <div className="flex flex-col items-center gap-2 px-5 text-center text-sm">
            <CameraOff size={26} />
            <span role="alert">{error}</span>
          </div>
        )}
      </div>
      {error && state !== 'error' && <p role="alert" className="mt-2 text-sm font-medium text-bad">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {(state === 'idle' || state === 'error') && (
          <button type="button" onClick={start} className="btn-primary"><Video size={16} /> {state === 'error' ? 'Try again' : 'Start camera'}</button>
        )}
        {state === 'live' && (
          <>
            <button type="button" onClick={capture} disabled={busy} className="btn-primary"><Camera size={16} /> Capture</button>
            <button type="button" onClick={() => { stop(); setState('idle'); }} className="btn-ghost">Stop camera</button>
          </>
        )}
        {state === 'captured' && (
          <button type="button" onClick={start} disabled={busy} className="btn-ghost"><RefreshCw size={16} /> Retake</button>
        )}
        {busy && state === 'captured' && <span role="status" className="inline-flex items-center gap-2 text-sm text-ink/65"><LoaderCircle size={15} className="animate-spin" /> Reading the sheet...</span>}
      </div>
    </section>
  );
};

export default WebcamCard;
