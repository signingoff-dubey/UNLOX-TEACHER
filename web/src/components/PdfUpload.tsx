import React, { useEffect, useRef, useState } from "react";
import { api, runJob, url } from "../api";
import type { Job, UploadStatus } from "../types";

type Props = {
  sha: string | null;
  onSha: (sha: string | null) => void;
  focus: string;
  onFocus: (focus: string) => void;
  disabled: boolean;
};

/** Upload with progress. fetch() cannot report upload progress, so this uses XMLHttpRequest. */
function sendPdf(file: File, onProgress: (fraction: number) => void): Promise<Job> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url("/api/uploads"));
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as Job);
      else reject(new Error(body?.detail ?? `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Upload failed: backend not reachable"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** Lesson source: a textbook or notes PDF (up to 2 GB / 5,000 pages), read offline with OCR. */
export const PdfUpload: React.FC<Props> = ({ sha, onSha, focus, onFocus, disabled }) => {
  const input = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [phase, setPhase] = useState<"idle" | "uploading" | "reading" | "done">("idle");
  const [pct, setPct] = useState(0);
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [error, setError] = useState("");

  // After the first pass, keep polling while scanned pages are being upgraded in the background.
  useEffect(() => {
    if (!sha) return;
    let stop = false;
    const tick = () =>
      api<UploadStatus>(`/api/uploads/${sha}`)
        .then((s) => {
          if (stop) return;
          setStatus(s);
          if (s.state !== "ready") setTimeout(tick, 3000);
        })
        .catch(() => !stop && setTimeout(tick, 5000));
    tick();
    return () => { stop = true; };
  }, [sha]);

  async function choose(file: File | undefined) {
    if (!file) return;
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
      setError("Please choose a PDF file.");
      return;
    }
    setError("");
    setName(file.name);
    setStatus(null);
    onSha(null);
    setPhase("uploading");
    setPct(0);
    try {
      const job = await runJob(sendPdf(file, setPct), (j) => {
        setPhase("reading");
        setStage(j.stage);
        setPct(j.progress);
      });
      const id = job.result?.sha as string | undefined;
      if (!id) throw new Error("Upload finished without an id");
      onSha(id);
      setPhase("done");
    } catch (e) {
      setPhase("idle");
      setError((e as Error).message);
    }
  }

  function clear() {
    onSha(null);
    onFocus("");
    setName("");
    setStatus(null);
    setPhase("idle");
    if (input.current) input.current.value = "";
  }

  const busy = phase === "uploading" || phase === "reading";
  let line = "";
  if (phase === "uploading") line = `Uploading ${Math.round(pct * 100)}%`;
  else if (phase === "reading") line = `${stage || "Reading pages"} ${Math.round(pct * 100)}%`;
  else if (status) {
    if (status.state === "ocr") line = `OCR ${status.tesseract_done} / ${status.scanned} scanned pages`;
    else if (status.state === "upgrading")
      line = `Ready · ${status.pages} pages · improving scans ${status.unlimited_done} / ${status.scanned}`;
    else line = `Ready · ${status.pages} pages` + (status.low_confidence ? ` · ${status.low_confidence} hard to read` : "");
  }

  return (
    <div className="upload">
      <div className="label">From a PDF <span className="muted">(optional textbook or notes)</span></div>
      {!name ? (
        <button type="button" className="drop" disabled={disabled}
          onClick={() => input.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); if (!disabled) choose(e.dataTransfer.files[0]); }}>
          <b>Choose a PDF</b>
          <span className="muted">or drop it here · up to 2 GB, scanned pages are read with OCR</span>
        </button>
      ) : (
        <div className="file">
          <div className="file-row">
            <span className="file-name" title={name}>{name}</span>
            <button type="button" className="link" onClick={clear} disabled={busy || disabled}>Remove</button>
          </div>
          {line && <div className="muted" role="status">{line}</div>}
          {(busy || status?.state === "ocr") && (
            <div className="bar"><div style={{
              transform: `scaleX(${busy ? pct : status ? status.tesseract_done / Math.max(status.scanned, 1) : 0})`,
            }} /></div>
          )}
          {sha && (
            <input className="focus" value={focus} onChange={(e) => onFocus(e.target.value)} disabled={disabled}
              placeholder="Chapter or pages (optional), e.g. chapter 4 or pages 120-135" maxLength={100}
              aria-label="Chapter or pages to teach" />
          )}
        </div>
      )}
      <input ref={input} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => choose(e.target.files?.[0])} />
      {error && <div className="error" role="alert">{error}</div>}
    </div>
  );
};
