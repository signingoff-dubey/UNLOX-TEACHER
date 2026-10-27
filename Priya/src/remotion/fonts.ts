import { useEffect, useState } from "react";
import { continueRender, delayRender } from "remotion";

// Files written by backend/scripts/download_models.py into web/public/fonts, served at /fonts.
const FONT_FILES: [string, string][] = [
  ["Noto Sans", "NotoSans.ttf"],
  ["Noto Sans Devanagari", "NotoSansDevanagari.ttf"],
  ["Noto Sans Telugu", "NotoSansTelugu.ttf"],
  ["Noto Sans Kannada", "NotoSansKannada.ttf"],
  ["Noto Sans Tamil", "NotoSansTamil.ttf"],
  ["Noto Sans Malayalam", "NotoSansMalayalam.ttf"],
  ["Noto Sans Bengali", "NotoSansBengali.ttf"],
  ["Noto Sans Gujarati", "NotoSansGujarati.ttf"],
];

let loading: Promise<void> | null = null;

export function loadFonts(assetBase: string): Promise<void> {
  loading ??= Promise.all(
    FONT_FILES.map(async ([family, file]) => {
      try {
        const face = new FontFace(family, `url(${assetBase}/fonts/${file})`, { weight: "100 900" });
        await face.load();
        document.fonts.add(face);
      } catch {
        // Missing font: the browser falls back to system fonts (Nirmala UI on Windows).
      }
    }),
  ).then(() => undefined);
  return loading;
}

/** Holds the frame until fonts are ready, so Indic text never renders in a fallback face. */
export function useFonts(assetBase: string) {
  const [handle] = useState(() => delayRender("Loading fonts"));
  useEffect(() => {
    loadFonts(assetBase).then(() => continueRender(handle));
  }, [assetBase, handle]);
}
