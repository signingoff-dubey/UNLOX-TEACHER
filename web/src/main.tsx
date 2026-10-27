import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { getApiBase } from "./api";
import { loadFonts } from "./remotion/fonts";
import { RewardsProvider } from "./rewards/RewardsContext";
import "@fontsource/figtree/400.css";
import "@fontsource/figtree/500.css";
import "@fontsource/figtree/600.css";
import "./styles/ds.css";
import "./styles/shell.css";
import "./styles/parts.css";
import "./styles/metaverse.css";
import "./styles/home.css";
import "./styles/scroll.css";

loadFonts(getApiBase());
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RewardsProvider>
      <App />
    </RewardsProvider>
  </React.StrictMode>,
);
