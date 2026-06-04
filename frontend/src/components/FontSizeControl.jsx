import React, { useEffect, useState } from "react";

const SIZES = ["normal", "large", "xl"];
const LABELS = { normal: "Normal", large: "Grande", xl: "Máx" };
const SCALES = { normal: "", large: "large", xl: "xl" };
const STORAGE_KEY = "asofamech-fontsize";

function getStored() {
  try { return localStorage.getItem(STORAGE_KEY) || "normal"; } catch { return "normal"; }
}

function applySize(key) {
  const attr = SCALES[key] || "";
  if (attr) {
    document.documentElement.setAttribute("data-fontsize", attr);
  } else {
    document.documentElement.removeAttribute("data-fontsize");
  }
  document.documentElement.style.fontSize = key === "large" ? "112.5%" : key === "xl" ? "125%" : "";
  try { localStorage.setItem(STORAGE_KEY, key); } catch {}
}

export function FontSizeControl() {
  const [current, setCurrent] = useState(() => getStored());
  const idx = SIZES.indexOf(current);

  useEffect(() => { applySize(current); }, []);

  const change = (key) => { setCurrent(key); applySize(key); };

  return (
    <div className="fontsize-control" aria-label="Tamaño de texto">
      <button
        type="button"
        className="fontsize-btn"
        onClick={() => change(SIZES[idx - 1])}
        disabled={idx === 0}
        aria-label="Reducir tamaño de texto"
        title="Reducir texto"
      >A−</button>
      <span className="fontsize-sep">{LABELS[current]}</span>
      <button
        type="button"
        className="fontsize-btn"
        onClick={() => change(SIZES[idx + 1])}
        disabled={idx === SIZES.length - 1}
        aria-label="Aumentar tamaño de texto"
        title="Agrandar texto"
      >A+</button>
    </div>
  );
}

export function FontSizeControlSidebar() {
  const [current, setCurrent] = useState(() => getStored());
  const idx = SIZES.indexOf(current);

  useEffect(() => { applySize(current); }, []);

  const change = (key) => { setCurrent(key); applySize(key); };

  return (
    <div className="fontsize-control-sidebar" aria-label="Tamaño de texto">
      <span className="fontsize-label">Tamaño texto</span>
      <div className="fontsize-btns">
        <button
          type="button"
          className="fontsize-btn"
          onClick={() => change(SIZES[idx - 1])}
          disabled={idx === 0}
          aria-label="Reducir tamaño de texto"
          title="Reducir"
        >A−</button>
        <span className="fontsize-sep">{LABELS[current]}</span>
        <button
          type="button"
          className="fontsize-btn"
          onClick={() => change(SIZES[idx + 1])}
          disabled={idx === SIZES.length - 1}
          aria-label="Aumentar tamaño de texto"
          title="Agrandar"
        >A+</button>
      </div>
    </div>
  );
}
