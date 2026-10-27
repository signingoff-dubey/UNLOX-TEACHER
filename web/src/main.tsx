import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { getApiBase } from "./api";
import { loadFonts } from "./remotion/fonts";
import "./app.css";
import "./screens.css";

loadFonts(getApiBase());
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
