import { useEffect, useState } from 'react';
import { CircleCheck, LoaderCircle, PhoneCall, PhoneMissed, PhoneOff } from 'lucide-react';
import { api } from '../lib/api';

// Live status of one alert call. Sarvam reports the outcome once, when the call ends (webhook), so while the
// call is going the pill shows "Dialing" with a running timer, then switches to the outcome and talk time.
const POLL_MS = 3000;
const ICON = { dialing: PhoneCall, connected: CircleCheck, no_answer: PhoneMissed, busy: PhoneOff, failed: PhoneOff };
const TONE = { dialing: 'bg-accent/20 text-white', connected: 'bg-good/20 text-white', no_answer: 'bg-warn/25 text-white', busy: 'bg-warn/25 text-white', failed: 'bg-bad/25 text-white' };
const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

const CallStatus = ({ id }) => {
  const [call, setCall] = useState(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!id) return undefined;
    let stop = false;
    let timer = 0;
    const started = Date.now();
    const poll = async () => {
      try {
        const c = await api(`/api/alerts/calls/${encodeURIComponent(id)}`);
        if (stop) return;
        setCall(c);
        if (c.status !== 'dialing' || Date.now() - started > 15 * 60000) return;
      } catch {
        // keep trying; the status endpoint can be cold for a few seconds
      }
      if (!stop) timer = setTimeout(poll, POLL_MS);
    };
    poll();
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      stop = true;
      clearTimeout(timer);
      clearInterval(tick);
    };
  }, [id]);

  if (!id || !call) return null;
  const Icon = ICON[call.status] ?? PhoneCall;
  const dialing = call.status === 'dialing';
  const since = Math.max(0, (now - new Date(call.at).getTime()) / 1000);
  return (
    <details className="group relative">
      <summary className={`flex cursor-pointer list-none items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ${TONE[call.status] ?? TONE.dialing}`}>
        {dialing ? <LoaderCircle size={14} className="animate-spin" /> : <Icon size={14} />}
        <span>{call.label}</span>
        <span className="tabular text-xs opacity-80">
          {dialing ? clock(since) : call.duration_s != null ? `talked ${clock(call.duration_s)}` : ''}
        </span>
      </summary>
      <div className="popover absolute right-0 z-20 mt-2 w-80 p-3.5 text-sm">
        <p className="font-semibold">{call.subject}</p>
        <p className="mt-1 text-xs text-white/60">To the number ending {call.to}. {dialing ? (call.note || 'Waiting for Sarvam to report how the call ended.') : `Ended ${new Date(call.ended_at).toLocaleTimeString()}.`}</p>
        {call.failure_reason && <p className="mt-1 text-xs text-red-300">{call.failure_reason}</p>}
        {call.transcript?.length > 0 && (
          <ul className="mt-2 max-h-56 overflow-y-auto rounded-xl bg-white/8 p-2 text-xs">
            {call.transcript.map((t, i) => (
              <li key={i} className="py-0.5"><span className="font-semibold capitalize">{t.role === 'agent' ? 'RootLens' : 'You'}:</span> {t.text}</li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
};

export default CallStatus;
