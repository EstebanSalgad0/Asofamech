import React, { useEffect, useState } from "react";
import { fetchCases } from "../api";

export function CaseList({ onAsk }) {
  const [cases, setCases] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchCases();
        setCases(data);
      } catch (e) {
        console.error("Error al cargar casos", e);
      }
    })();
  }, []);

  if (!cases.length) return null;

  return (
    <div style={{ marginTop: 24 }}>
      <h2>Casos clínicos disponibles (modo estudio)</h2>
      <ul>
        {cases.map((c) => (
          <li key={c.id} style={{ marginBottom: 8 }}>
            <strong>{c.title}</strong>
            <p style={{ margin: "4px 0" }}>{c.description}</p>
            <button onClick={() => onAsk(`Analicemos el caso clínico: ${c.title}`)}>
              Preguntar al asistente sobre este caso
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
