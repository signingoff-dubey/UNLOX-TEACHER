import { useEffect, useState } from 'react';
import { BellRing, Loader2, Mail, MessageCircle, PhoneCall, Send } from 'lucide-react';
import { CardTitle, Toggle } from '../ui';
import { api, post } from '../../lib/api';

// Defect alerts: the API watches new scans, models and captures, and phones / WhatsApps / emails
// the plant contact as soon as a crack (or another enabled trigger) shows up.

const CHANNELS = [
  { id: 'call', label: 'Phone call', icon: PhoneCall, recipient: 'phone', placeholder: '919876543210', hint: 'A voice agent calls, says where the fault is and answers questions.' },
  { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircle, recipient: 'whatsapp', placeholder: '919876543210', hint: 'A WhatsApp message to the whole team. Separate numbers with commas.' },
  { id: 'email', label: 'Email', icon: Mail, recipient: 'email', placeholder: 'manager@plant.com', hint: 'An email with the details.' },
];
const PROVIDER = { sarvam: 'Sarvam voice agent', twilio: 'Twilio', smtp: 'SMTP' };
const put = (path, body) => api(path, { method: 'PUT', body: JSON.stringify(body) });
const when = (iso) => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

const Chip = ({ ok, children }) => (
  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${ok ? 'bg-good/15 text-good' : 'bg-ink/8 text-ink/55'}`}>
    <span className={`size-1.5 rounded-full ${ok ? 'bg-good' : 'bg-ink/35'}`} />
    {children}
  </span>
);

const ChannelRow = ({ ch, data, onSettings, onTest, testing }) => {
  const s = data.settings;
  const provider = data.configured[ch.id];
  const [value, setValue] = useState(s.recipients[ch.recipient] ?? '');
  useEffect(() => setValue(s.recipients[ch.recipient] ?? ''), [s.recipients, ch.recipient]);
  const Icon = ch.icon;
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-ink/10 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-xl bg-accent/15 text-accent-deep"><Icon size={17} /></span>
          <span>
            <span className="block text-sm font-semibold">{ch.label}</span>
            <span className="block text-xs text-ink/55">{ch.hint}</span>
          </span>
        </span>
        <span className="flex items-center gap-3">
          <Chip ok={!!provider}>{provider ? `Ready: ${PROVIDER[provider] ?? provider}` : 'Needs keys in .env'}</Chip>
          <Toggle checked={!!s.channels[ch.id]} onChange={(on) => onSettings({ channels: { [ch.id]: on } })} label={`${ch.label} alerts`} />
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => value !== s.recipients[ch.recipient] && onSettings({ recipients: { [ch.recipient]: value.trim() } })}
          placeholder={ch.placeholder}
          aria-label={`${ch.label} recipient`}
          inputMode={ch.id === 'email' ? 'email' : 'tel'}
          className="field min-w-0 flex-1 font-mono"
        />
        <button type="button" onClick={() => onTest(ch.id)} disabled={testing === ch.id} className="btn-ghost h-10 px-4 text-sm">
          {testing === ch.id ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send test
        </button>
      </div>
    </div>
  );
};

const AlertsTab = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [testing, setTesting] = useState(null);

  const load = () => api('/api/alerts').then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const onSettings = async (patch) => {
    try {
      const settings = await put('/api/alerts/settings', patch);
      setData((d) => ({ ...d, settings }));
    } catch (e) {
      setError(e.message);
    }
  };
  const onTest = async (channel) => {
    setTesting(channel);
    try {
      await post('/api/alerts/test', { channel }, { signal: AbortSignal.timeout(30000) });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setTesting(null);
    }
  };

  if (!data) {
    return (
      <section className="card text-sm text-ink/65">
        {error ? `Could not reach the API: ${error}` : <span className="flex items-center gap-2"><Loader2 size={15} className="animate-spin" /> Loading alert settings...</span>}
      </section>
    );
  }
  const s = data.settings;

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-2">
      <section className="card xl:col-span-2">
        <CardTitle
          sub="As soon as a new inspection finds a crack, RootLens calls, messages and emails the people below."
          action={<Toggle checked={s.enabled} onChange={(enabled) => onSettings({ enabled })} label="Defect alerts" />}
        >
          <span className="flex items-center gap-2"><BellRing size={17} /> Defect alerts</span>
        </CardTitle>
        <p className="mb-3 flex items-center gap-2 text-sm">
          <Chip ok={data.watching && s.enabled}>{!s.enabled ? 'Off' : data.watching ? `Watching, checks every ${data.poll_s} s` : 'Starts with the API'}</Chip>
          {data.pending > 0 && <Chip ok={false}>{data.pending} finding{data.pending === 1 ? '' : 's'} waiting for the batch to finish</Chip>}
          <span className="text-xs text-ink/55">One alert per batch, sent {data.quiet_s} s after the last upload or inspection finishes.</span>
        </p>
        <div className="grid gap-3 lg:grid-cols-3">
          {CHANNELS.map((ch) => <ChannelRow key={ch.id} ch={ch} data={data} onSettings={onSettings} onTest={onTest} testing={testing} />)}
        </div>
        {error && <p role="alert" className="mt-3 rounded-xl bg-bad/12 px-3 py-2 text-sm">{error}</p>}
      </section>

      <section className="card">
        <CardTitle sub="Which findings send an alert.">Triggers</CardTitle>
        <div className="flex flex-col gap-2">
          {Object.entries(data.triggers).map(([id, label]) => (
            <div key={id} className="flex items-center justify-between gap-3 rounded-xl border border-ink/10 px-3 py-2.5 text-sm">
              <span className="font-medium">{label}</span>
              <Toggle checked={!!s.triggers[id]} onChange={(on) => onSettings({ triggers: { [id]: on } })} label={label} />
            </div>
          ))}
          <p className="text-xs text-ink/55">Calls are spaced at least {s.call_min_gap_min} min apart, at most {s.calls_per_day} a day. Messages and emails are not limited.</p>
        </div>
      </section>

      {data.calls?.length > 0 && (
        <section className="card xl:col-span-2">
          <CardTitle sub="Sarvam reports how each call ended (picked up and talk time, not picked up, declined, failed). Refreshes every 5 s.">Calls</CardTitle>
          <ul className="flex flex-col gap-1.5">
            {data.calls.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-ink/5 px-3 py-2 text-sm">
                <span className="min-w-0 truncate font-medium">{c.subject}</span>
                <span className="flex items-center gap-2 text-xs">
                  <span className={`rounded-full px-2 py-0.5 font-semibold ${c.status === 'connected' ? 'bg-good/15 text-good' : c.status === 'dialing' ? 'bg-accent/15 text-accent-deep' : 'bg-warn/15 text-warn'}`}>{c.label}</span>
                  {c.duration_s != null && <span className="tabular">{Math.floor(c.duration_s / 60)}:{String(Math.round(c.duration_s % 60)).padStart(2, '0')}</span>}
                  <span className="text-ink/50">{when(c.at)}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <CardTitle sub="Newest first.">Sent alerts</CardTitle>
        {data.log.length === 0 ? (
          <p className="text-sm text-ink/55">No alerts yet. Use Send test to check a channel.</p>
        ) : (
          <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto pr-1">
            {data.log.map((e, i) => (
              <li key={`${e.at}-${e.channel}-${i}`} className="rounded-xl bg-ink/5 px-3 py-2 text-sm">
                <p className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{e.subject}</span>
                  <span className="shrink-0 text-xs text-ink/50">{when(e.at)}</span>
                </p>
                <p className="mt-0.5 flex items-center gap-2 text-xs">
                  <span className={`rounded-full px-2 py-0.5 font-semibold capitalize ${e.ok ? 'bg-good/15 text-good' : 'bg-bad/12 text-bad'}`}>{e.channel}</span>
                  <span className="truncate text-ink/60">{e.result}</span>
                  {e.link && <a href={e.link} className="ml-auto shrink-0 font-medium text-accent-deep hover:underline">Open</a>}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};

export default AlertsTab;
