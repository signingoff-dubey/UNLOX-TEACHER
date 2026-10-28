import React from "react";
import { Ui } from "../components/ui-icons";
import type { ToolState } from "./useStudio";
import { useSteadyProgress } from "./useSteadyProgress";
import type { StudioKind } from "./types";

type Props = {
  kind: StudioKind;
  label: string;
  hint: string;
  state: ToolState | undefined;
  /** Clicked while it was not built yet: it is at the front of the queue and will open when it is done. */
  wanted: boolean;
  disabled: boolean;
  onClick: () => void;
};

/**
 * One study-tool button. Ready: opens at once. Working (being written now, or clicked and next in line): a border of
 * flowing colour runs around it and a steady percentage counts up. Waiting in the queue unclicked: plain.
 */
export const StudioButton: React.FC<Props> = ({ kind, label, hint, state, wanted, disabled, onClick }) => {
  const building = state?.state === "building";
  const busy = wanted || building;
  const shown = useSteadyProgress(state?.progress ?? 0, busy);
  const pct = Math.floor(shown * 100);
  const ready = state?.state === "ready";
  const cls = ["studio-btn", ready ? "is-ready" : "", busy ? "is-busy" : "", state?.state === "error" ? "is-error" : ""].join(" ");
  return (
    <button type="button" className={cls} disabled={disabled} aria-busy={busy} onClick={onClick}
      style={{ ["--p" as string]: busy ? Math.round(shown * 100) : ready ? 100 : 0 }}
      title={ready ? hint : busy ? `${state?.stage || "Starting"} (${pct}%)` : hint}>
      {busy ? <span className="sb-pct">{pct}%</span> : <Ui name={kind} size={16} />}
      {label}
      <span className="sr-only">{ready ? ", ready" : busy ? `, ${pct} percent` : ""}</span>
    </button>
  );
};

/** The Meta quiz button: same flow while the world is being built from everything the AI wrote. */
export const MetaButton: React.FC<{ busy: { progress: number; stage: string } | null | undefined; disabled: boolean; onClick: () => void }> = ({ busy, disabled, onClick }) => {
  const shown = useSteadyProgress(busy?.progress ?? 0, !!busy);
  const pct = Math.floor(shown * 100);
  return (
    <button type="button" className={`studio-btn meta${busy ? " is-busy" : ""}`} disabled={disabled} aria-busy={!!busy} onClick={onClick}
      style={{ ["--p" as string]: busy ? Math.round(shown * 100) : 0 }}
      title={busy ? `${busy.stage} (${pct}%)` : "Play a metaverse world built from everything the AI wrote for this video (or every video of the course)"}>
      {busy ? <span className="sb-pct">{pct}%</span> : <Ui name="cube" size={16} />}
      Meta quiz
    </button>
  );
};
