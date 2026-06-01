"use client";

import { useEffect, useState } from "react";
import type { GenerateResponse, RefineResponse } from "../lib/types";

interface Props {
  result: GenerateResponse | RefineResponse;
}

export function DiagramView({ result }: Props) {
  const svg = result.artifacts.find((a) => a.kind === "svg");
  const [svgMarkup, setSvgMarkup] = useState<string | null>(null);

  useEffect(() => {
    if (!svg) return;
    let cancelled = false;
    void fetch(svg.url)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((text) => {
        if (!cancelled) setSvgMarkup(text);
      })
      .catch(() => {
        if (!cancelled) setSvgMarkup(null);
      });
    return () => {
      cancelled = true;
    };
  }, [svg]);

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 8,
        background: "white",
        padding: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        minHeight: "60vh",
      }}
    >
      <div style={{ flex: 1, overflow: "auto", display: "flex", justifyContent: "center" }}>
        {svgMarkup ? (
          // biome-ignore lint/security/noDangerouslySetInnerHtml: SVG from our own backend
          <div dangerouslySetInnerHTML={{ __html: svgMarkup }} />
        ) : svg ? (
          <img src={svg.url} alt="Generated architecture diagram" style={{ maxWidth: "100%" }} />
        ) : (
          <div>SVG unavailable</div>
        )}
      </div>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {result.artifacts.map((a) => (
          <a key={a.kind} href={a.url} download>
            <button type="button">download .{a.kind}</button>
          </a>
        ))}
      </div>
      <details style={{ color: "#333" }}>
        <summary style={{ cursor: "pointer", color: "#0078d4" }}>pattern descriptor (JSON)</summary>
        <pre
          style={{
            background: "#f4f4f4",
            padding: "0.5rem",
            borderRadius: 4,
            overflow: "auto",
            fontSize: "0.75rem",
            maxHeight: "30vh",
          }}
        >
          {JSON.stringify(result.pattern, null, 2)}
        </pre>
      </details>
    </div>
  );
}
