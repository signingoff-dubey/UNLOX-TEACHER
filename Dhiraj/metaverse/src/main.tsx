import React from "react";
import { createRoot } from "react-dom/client";
import Metaverse from "./index";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <div style={{ position: "fixed", inset: 0 }}>
      <Metaverse />
    </div>
  </React.StrictMode>,
);
