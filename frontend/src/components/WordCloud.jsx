import React, { useMemo, useState } from "react";

/**
 * Nube de palabras de las respuestas abiertas.
 *
 * Se dibuja con texto en flujo y no con un layout en espiral sobre canvas: el
 * texto real se puede seleccionar, copiar y leer con lector de pantalla, y a
 * este volumen (unas decenas de terminos) la espiral solo aportaria ruido
 * visual. El tamaño codifica la frecuencia; el color, su intensidad relativa.
 *
 * Las palabras se barajan con una permutacion estable —derivada del propio
 * termino— para que no queden ordenadas por tamaño de mayor a menor, que es lo
 * que hace que una nube parezca una lista.
 */

const MIN_FONT = 13;
const MAX_FONT = 42;

/** Hash estable de una cadena: mismo termino, misma posicion entre recargas. */
function stableHash(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

export function WordCloud({ words, emptyLabel = "Sin respuestas para analizar todavía." }) {
  const [selected, setSelected] = useState(null);

  const laidOut = useMemo(() => {
    if (!words || words.length === 0) return [];
    const counts = words.map((word) => word.count);
    const max = Math.max(...counts);
    const min = Math.min(...counts);
    const span = Math.max(1, max - min);

    return words
      .map((word) => {
        const weight = (word.count - min) / span; // 0..1
        return {
          ...word,
          // Raiz cuadrada: sin ella, un termino que aparece el doble de veces se
          // ve cuatro veces mas grande (el area crece con el cuadrado) y aplasta
          // al resto de la nube.
          fontSize: Math.round(MIN_FONT + Math.sqrt(weight) * (MAX_FONT - MIN_FONT)),
          weight,
          order: stableHash(word.text),
        };
      })
      .sort((a, b) => a.order - b.order);
  }, [words]);

  if (laidOut.length === 0) {
    return <p className="wc-empty">{emptyLabel}</p>;
  }

  return (
    <div className="wc">
      <div className="wc-canvas" role="list">
        {laidOut.map((word) => (
          <button
            key={word.text}
            type="button"
            role="listitem"
            className={`wc-word ${selected === word.text ? "selected" : ""}`}
            style={{
              fontSize: `${word.fontSize}px`,
              opacity: 0.55 + word.weight * 0.45,
            }}
            title={`${word.count} menciones en ${word.responses} respuesta(s)`}
            onClick={() => setSelected(selected === word.text ? null : word.text)}
          >
            {word.text}
          </button>
        ))}
      </div>
      {selected && (
        <p className="wc-detail">
          {(() => {
            const word = laidOut.find((w) => w.text === selected);
            if (!word) return null;
            return (
              <>
                <strong>{word.text}</strong> — {word.count}{" "}
                {word.count === 1 ? "mención" : "menciones"} en {word.responses}{" "}
                {word.responses === 1 ? "respuesta" : "respuestas"}.
              </>
            );
          })()}
        </p>
      )}
    </div>
  );
}

export default WordCloud;
