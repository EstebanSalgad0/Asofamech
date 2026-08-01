import React from "react";
import { CaseImageFigure } from "./CaseImageGallery";

/**
 * Renderiza el cuerpo de un caso clinico escrito en markdown ligero.
 *
 * Devuelve elementos de React en vez de HTML como texto: asi el contenido del
 * caso nunca se interpreta como marcado ejecutable, y permite intercalar las
 * imagenes del caso como componentes reales (con su lightbox) en el punto
 * exacto donde el docente las coloco.
 *
 * Soporta: encabezados ##/###, listas con - o numeradas, tablas, **negrita**,
 * *cursiva* y el marcador [[imagen:N]], donde N es la posicion de la imagen
 * dentro del caso empezando en 1.
 */

const IMAGE_PLACEHOLDER = /\[\[imagen:(\d+)\]\]/i;

function renderInline(text, keyPrefix) {
  // Se procesa negrita y cursiva en una sola pasada para no anidar mal.
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const key = `${keyPrefix}-i${index++}`;
    if (token.startsWith("**")) {
      parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("`")) {
      parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else {
      parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length > 0 ? parts : text;
}

function splitRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

const isTableSeparator = (line) => /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(line) && line.includes("-");

export function CaseBody({ body, images = [] }) {
  const usedImagePositions = new Set();
  const lines = (body || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];

  let listBuffer = [];
  let listOrdered = false;
  let paragraphBuffer = [];

  const flushList = () => {
    if (listBuffer.length === 0) return;
    const Tag = listOrdered ? "ol" : "ul";
    const items = listBuffer;
    blocks.push(
      <Tag key={`list-${blocks.length}`} className="case-body-list">
        {items.map((item, i) => (
          <li key={i}>{renderInline(item, `l${blocks.length}-${i}`)}</li>
        ))}
      </Tag>
    );
    listBuffer = [];
  };

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) return;
    const text = paragraphBuffer.join(" ");
    paragraphBuffer = [];
    blocks.push(
      <p key={`p-${blocks.length}`} className="case-body-paragraph">
        {renderInline(text, `p${blocks.length}`)}
      </p>
    );
  };

  const flushAll = () => {
    flushList();
    flushParagraph();
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trim();

    if (line === "") {
      flushAll();
      continue;
    }

    const placeholder = line.match(IMAGE_PLACEHOLDER);
    if (placeholder) {
      flushAll();
      const position = parseInt(placeholder[1], 10);
      const image = images[position - 1];
      if (image) {
        usedImagePositions.add(position);
        blocks.push(
          <CaseImageFigure key={`img-${image.id}`} image={image} variant="inline" />
        );
      }
      continue;
    }

    const heading = line.match(/^(#{2,4})\s+(.*)$/);
    if (heading) {
      flushAll();
      const level = heading[1].length;
      const Tag = `h${Math.min(level + 2, 6)}`;
      blocks.push(
        <Tag key={`h-${blocks.length}`} className={`case-body-h${level}`}>
          {renderInline(heading[2], `h${blocks.length}`)}
        </Tag>
      );
      continue;
    }

    // Tabla: fila de encabezado seguida de separador |---|---|
    if (line.startsWith("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      flushAll();
      const header = splitRow(line);
      const rows = [];
      let cursor = i + 2;
      while (cursor < lines.length && lines[cursor].trim().startsWith("|")) {
        rows.push(splitRow(lines[cursor]));
        cursor++;
      }
      blocks.push(
        <div key={`t-${blocks.length}`} className="case-body-table-wrap">
          <table className="case-body-table">
            <thead>
              <tr>
                {header.map((cell, ci) => (
                  <th key={ci}>{renderInline(cell, `th${ci}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td key={ci}>{renderInline(cell, `td${ri}-${ci}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      i = cursor - 1;
      continue;
    }

    const bullet = line.match(/^[-*+]\s+(.*)$/);
    if (bullet) {
      flushParagraph();
      if (listBuffer.length > 0 && listOrdered) flushList();
      listOrdered = false;
      listBuffer.push(bullet[1]);
      continue;
    }

    const ordered = line.match(/^\d+[.)]\s+(.*)$/);
    if (ordered) {
      flushParagraph();
      if (listBuffer.length > 0 && !listOrdered) flushList();
      listOrdered = true;
      listBuffer.push(ordered[1]);
      continue;
    }

    flushList();
    paragraphBuffer.push(line);
  }

  flushAll();

  // Cualquier imagen que el docente no haya colocado con [[imagen:N]] se muestra
  // al final: nunca se pierde una imagen cargada por no referenciarla.
  const trailing = images.filter((_, index) => !usedImagePositions.has(index + 1));

  return (
    <div className="case-body" data-testid="case-body">
      {blocks}
      {trailing.length > 0 && (
        <div className="case-img-grid">
          {trailing.map((image) => (
            <CaseImageFigure key={`extra-${image.id}`} image={image} variant="thumb" />
          ))}
        </div>
      )}
    </div>
  );
}

export default CaseBody;
