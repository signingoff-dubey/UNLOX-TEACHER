import { CloudOff, LoaderCircle, RefreshCw, TriangleAlert } from 'lucide-react';

// Loading, error and "not generated yet" states for anything fetched from the API.
// A 503 from the backend means the artifact has not been built (run `make train`), which is not a crash.
export const StatusCard = ({ q, what = 'This data' }) => {
  if (q.loading) {
    return (
      <section className="card flex items-center gap-3 text-sm text-ink/65" role="status" aria-live="polite">
        <LoaderCircle size={18} className="animate-spin" /> Loading {what.toLowerCase()}...
      </section>
    );
  }
  const notReady = q.error?.status === 503;
  const Icon = notReady ? CloudOff : TriangleAlert;
  return (
    <section className="card" role="alert">
      <div className="flex items-start gap-3">
        <Icon size={20} className="mt-0.5 shrink-0 text-ink/55" />
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-semibold">{notReady ? `${what} is not generated yet` : `${what} could not be loaded`}</p>
          <p className="mt-0.5 text-xs text-ink/60">
            {notReady ? 'The backend has not built this artifact. Run "make train" (or the matching stage) and try again.' : q.error?.status ? q.error.message : 'No answer from the API. Check that it is running and the address in Settings > Data.'}
          </p>
        </div>
        <button type="button" onClick={q.refetch} className="btn-ghost h-8 px-3 text-xs">
          <RefreshCw size={13} /> Retry
        </button>
      </div>
    </section>
  );
};

// <Gate q={useApi(path)} what="Ranking">{(data) => ...}</Gate>
const Gate = ({ q, what, children }) => (q.data ? children(q.data) : <StatusCard q={q} what={what} />);

export default Gate;
