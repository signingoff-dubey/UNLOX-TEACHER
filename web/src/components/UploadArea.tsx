import React, { useCallback, useRef, useState } from "react";
import { DocServiceOffline, uploadDocument, type DocInfo } from "../api";
import { Ui } from "./ui-icons";

export type UploadItem = {
  key: string;
  file: File;
  state: "uploading" | "done" | "offline" | "error";
  progress: number;
  doc?: DocInfo;
  error?: string;
};

const size = (b: number) => (b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);

/** Drag-and-drop PDF area. Files go to the document service (RAG + OCR); lessons are then grounded in them. */
export const UploadArea: React.FC<{
  items: UploadItem[];
  onChange: (update: (items: UploadItem[]) => UploadItem[]) => void;
  disabled?: boolean;
}> = ({ items, onChange, disabled }) => {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const add = useCallback((files: FileList | File[]) => {
    const pdfs = Array.from(files).filter((f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name));
    const fresh: UploadItem[] = pdfs.map((file) => ({
      key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`,
      file, state: "uploading", progress: 0,
    }));
    if (!fresh.length) return;
    onChange((cur) => [...cur, ...fresh]);
    const patch = (key: string, p: Partial<UploadItem>) =>
      onChange((cur) => cur.map((it) => (it.key === key ? { ...it, ...p } : it)));
    for (const it of fresh) {
      uploadDocument(it.file, (progress) => patch(it.key, { progress }))
        .then((doc) => patch(it.key, { state: "done", progress: 1, doc }))
        .catch((e) => patch(it.key, e instanceof DocServiceOffline
          ? { state: "offline" } : { state: "error", error: (e as Error).message }));
    }
  }, [onChange]);

  const remove = (key: string) => onChange((cur) => cur.filter((it) => it.key !== key));

  return (
    <div>
      <div
        className={`drop ${over ? "over" : ""} ${disabled ? "off" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) add(e.dataTransfer.files); }}
      >
        <Ui name="upload" size={30} />
        <div className="drop-title">Drop PDFs here</div>
        <div className="muted">Textbooks, notes, scans. Thousands of pages are fine.</div>
        <button type="button" className="ghost small-ghost" disabled={disabled} onClick={() => input.current?.click()}>
          Browse files
        </button>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
          onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = ""; }} />
      </div>

      {items.length > 0 && (
        <ul className="files" aria-label="Uploaded documents">
          {items.map((it) => (
            <li key={it.key} className={`file ${it.state}`}>
              <Ui name="file" size={20} />
              <div className="file-main">
                <div className="file-name" title={it.file.name}>{it.file.name}</div>
                <div className="muted file-meta">
                  {size(it.file.size)}
                  {it.state === "uploading" && ` · uploading ${Math.round(it.progress * 100)}%`}
                  {it.state === "done" && ` · ready${it.doc?.pages ? ` · ${it.doc.pages} pages` : ""}`}
                  {it.state === "offline" && " · document service not connected yet"}
                  {it.state === "error" && ` · ${it.error}`}
                </div>
                {it.state === "uploading" && (
                  <div className="bar thin"><div style={{ transform: `scaleX(${it.progress})` }} /></div>
                )}
              </div>
              <button type="button" className="icon-btn" aria-label={`Remove ${it.file.name}`} onClick={() => remove(it.key)}>
                <Ui name="x" size={18} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
