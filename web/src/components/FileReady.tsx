import React, { useEffect, useRef } from "react";
import { Ui } from "./ui-icons";

export type FileAction = { label: string; href: string; download?: string; newTab?: boolean };

/** Shown when a file the learner asked for is ready (an MP4, a whole course): save it, or open it. The first action is the main one. */
export const FileReady: React.FC<{ title: string; detail: string; actions: FileAction[]; onClose: () => void }> = ({ title, detail, actions, onClose }) => {
  const first = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    first.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previous?.focus?.(); };
  }, [onClose]);

  return (
    <div className="studio-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="paper-pop" role="dialog" aria-modal="true" aria-labelledby="file-pop-h">
        <button type="button" className="icon-btn paper-pop-x" onClick={onClose} aria-label="Close"><Ui name="x" size={18} /></button>
        <div className="paper-pop-badge" aria-hidden><Ui name="check" size={26} /></div>
        <h2 id="file-pop-h">{title}</h2>
        <p className="muted">{detail}</p>
        <div className="paper-pop-actions">
          {actions.map((a, i) => (
            <a key={a.label} ref={i === 0 ? first : undefined} className={`paper-pop-btn${i === 0 ? " main" : a.newTab ? " ghost" : ""}`} href={a.href}
              {...(a.newTab ? { target: "_blank", rel: "noopener" } : { download: a.download ?? "" })} onClick={a.newTab ? undefined : onClose}>
              <Ui name={a.newTab ? "play" : "download"} size={18} />{a.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
};
