import React from "react";

/** First thing you see after the tunnel: the metaverse, behind a Start button. Start reveals the topic screen. */
export const MetaverseStart: React.FC<{ onStart: () => void; onBack: () => void }> = ({ onStart, onBack }) => (
  <div className="mv-start" role="dialog" aria-labelledby="mv-start-h">
    <div className="mv-start-card">
      <div className="mv-start-eyebrow">Learnverse</div>
      <h1 id="mv-start-h">Step into your lesson</h1>
      <p>Every topic becomes a place you can walk through. Pass the quiz gates, earn points, and spend them in the shop.</p>
      <button type="button" className="mv-start-btn" onClick={onStart} autoFocus>Start</button>
      <button type="button" className="mv-start-back" onClick={onBack}>Back to Visual Teacher</button>
    </div>
  </div>
);
