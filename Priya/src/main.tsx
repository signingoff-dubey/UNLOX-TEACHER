import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { getApiBase } from "./api";
import { loadFonts } from "./remotion/fonts";
import "@fontsource/figtree/400.css";
import "@fontsource/figtree/500.css";
import "@fontsource/figtree/600.css";
import "./app.css";

loadFonts(getApiBase());
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
