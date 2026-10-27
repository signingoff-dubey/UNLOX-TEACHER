import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadFonts } from "./remotion/fonts";
import "./app.css";

loadFonts("");
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
