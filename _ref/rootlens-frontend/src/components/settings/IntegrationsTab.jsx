import { useEffect, useState } from 'react';
import { Box, Crosshair, Layers, Loader2, Mail, MessageCircle, PhoneCall, RefreshCw, TriangleAlert } from 'lucide-react';
import { CardTitle, Toggle } from '../ui';
import { api, post } from '../../lib/api';

// Blender link through the Blender MCP add-on: RootLens reads the open scene, lists the objects
// that carry a defect and can frame one of them in the engineer's Blender viewport.

const put = (path, body) => api(path, { method: 'PUT', body: JSON.stringify(body) });
const fmt = (v) => v.map((x) => x.toFixed(2)).join(', ');

const State = ({ s }) => {
  const map = {
    connected: ['bg-good/15 text-good', 'bg-good animate-pulse', 'Connected'],
    offline: ['bg-bad/12 text-bad', 'bg-bad', 'Not reachable'],
    off: ['bg-ink/8 text-ink/55', 'bg-ink/35', 'Not connected'],
  };
  const [cls, dot, label] = map[s] ?? map.off;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>
      <span className={`size-1.5 rounded-full ${dot}`} /> {label}
    </span>
  );
};

// Where alerts and reports can go. The agent call is live; the others can be connected to the same alert
// pipeline and are shown switched off until they are set up.
const CHANNELS = [
  { name: 'Agent call', icon: PhoneCall, on: true, what: 'Calls the plant manager with the damage report and answers questions on the call.' },
  { name: 'WhatsApp', icon: MessageCircle, on: false, what: 'Sends the damage report and the suggested fix as a WhatsApp message.' },
  { name: 'Email', icon: Mail, on: false, what: 'Emails the report, the safe windows and the savings range to the quality team.' },
  { name: 'CMS', icon: Layers, on: false, what: "Publishes reports and fixes to the plant's content management system." },
];

const Channel = ({ c }) => (
  <div className={`flex items-start gap-3 rounded-2xl p-4 ring-1 ${c.on ? 'bg-accent/8 ring-accent/25' : 'bg-ink/5 ring-ink/8'}`}>
    <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${c.on ? 'bg-accent text-on-accent' : 'bg-ink/10 text-ink/55'}`}><c.icon size={18} /></span>
    <div className="min-w-0 flex-1">
      <div className="flex items-center gap-2">
        <p className="font-semibold">{c.name}</p>
        <State s={c.on ? 'connected' : 'off'} />
      </div>
      <p className="mt-1 text-sm text-ink/65">{c.what}</p>
    </div>
    <Toggle checked={c.on} onChange={() => {}} label={`${c.name} ${c.on ? 'on' : 'off'}`} disabled />
  </div>
);

const IntegrationsTab = () => {
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState({});

  const load = () => api('/api/integrations/blender', { signal: AbortSignal.timeout(20000) })
    .then(setSt)
    .catch((e) => setSt((p) => ({ ...(p ?? {}), state: 'offline', connected: false, error: e.message })));
  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, []);

  const toggle = async (enabled) => {
    setBusy(true);
    try {
      setSt(await put('/api/integrations/blender', { enabled }));
    } finally {
      setBusy(false);
    }
  };
  const show = async (name) => {
    setFocus((f) => ({ ...f, [name]: 'busy' }));
    try {
      const r = await post('/api/integrations/blender/focus', { name });
      setFocus((f) => ({ ...f, [name]: r.ok ? 'done' : 'missing' }));
    } catch {
      setFocus((f) => ({ ...f, [name]: 'error' }));
    }
  };

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-2">
      <section className="card xl:col-span-2">
        <CardTitle
          sub="Link the plant's 3D model in Blender. RootLens finds the defects in the open scene and points to where each one lies."
          action={<Toggle checked={!!st?.enabled} onChange={toggle} label="Blender MCP link" />}
        >
          <span className="flex items-center gap-2"><Box size={17} /> Blender MCP</span>
        </CardTitle>

        {!st ? (
          <p className="flex items-center gap-2 text-sm text-ink/65"><Loader2 size={15} className="animate-spin" /> Checking the link...</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <State s={st.state} />
              <span className="font-mono text-xs text-ink/55">{st.host}:{st.port}</span>
              {st.connected && <span className="text-ink/70">{st.file} · {st.objects} objects · {st.defects?.length ?? 0} defects</span>}
              <button type="button" onClick={load} disabled={busy} className="btn-ghost ml-auto h-9 px-3 text-sm"><RefreshCw size={14} /> Refresh</button>
            </div>
            {st.state === 'offline' && (
              <p className="mt-3 rounded-xl bg-ink/5 px-3 py-2 text-sm text-ink/70">
                Open Blender with the BlenderMCP add-on, press N in the 3D view, open the BlenderMCP tab and click Connect to MCP server.
              </p>
            )}
          </>
        )}
      </section>

      <section className="card xl:col-span-2">
        <CardTitle sub="Where RootLens sends alerts and reports. Push notifications to the phone app are always on.">Alert and report channels</CardTitle>
        <div className="grid gap-3 md:grid-cols-2">
          {CHANNELS.map((c) => <Channel key={c.name} c={c} />)}
        </div>
      </section>

      {st?.connected && (
        <section className="card xl:col-span-2">
          <CardTitle sub="Objects in the open scene tagged with a defect, with their position in the model (Blender units).">Where the defects lie</CardTitle>
          {st.defects.length === 0 ? (
            <p className="text-sm text-ink/55">No defect objects in this scene.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="text-xs text-ink/55">
                  <tr><th className="py-1.5">Object</th><th>Defect</th><th>Position (x, y, z)</th><th>Size</th><th /></tr>
                </thead>
                <tbody>
                  {st.defects.map((d) => (
                    <tr key={d.name} className="border-t border-ink/8">
                      <td className="py-2 font-medium"><TriangleAlert size={13} className="mr-1.5 inline text-bad" />{d.part || d.name}</td>
                      <td className="capitalize text-ink/70">{d.type}</td>
                      <td className="tabular font-mono text-xs">{fmt(d.center)}</td>
                      <td className="tabular font-mono text-xs">{fmt(d.size)}</td>
                      <td className="text-right">
                        <button type="button" onClick={() => show(d.name)} disabled={focus[d.name] === 'busy'} className="btn-ghost h-8 px-3 text-xs">
                          {focus[d.name] === 'busy' ? <Loader2 size={13} className="animate-spin" /> : <Crosshair size={13} />}
                          {focus[d.name] === 'done' ? 'Shown in Blender' : focus[d.name] === 'error' ? 'Try again' : 'Show in Blender'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default IntegrationsTab;
