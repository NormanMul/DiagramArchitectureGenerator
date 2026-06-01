"use client";

import { useCallback, useState } from "react";
import type { GenerateResponse, RefineResponse } from "../lib/types";
import { DiagramView } from "./DiagramView";

type Turn =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; result: GenerateResponse | RefineResponse };

export function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sessionId = turns.find((t) => t.role === "assistant")?.result.session_id;
  const currentPattern = (() => {
    for (let i = turns.length - 1; i >= 0; i--) {
      const t = turns[i];
      if (t?.role === "assistant") return t.result.pattern;
    }
    return null;
  })();

  const submit = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    const userTurn: Turn = { role: "user", text: trimmed };
    setTurns((prev) => [...prev, userTurn]);
    setInput("");
    try {
      const path = currentPattern && sessionId ? "/api/refine" : "/api/generate";
      const body =
        currentPattern && sessionId
          ? {
              session_id: sessionId,
              instruction: trimmed,
              current_pattern: currentPattern,
            }
          : { prompt: trimmed };
      const resp = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
      }
      const result = (await resp.json()) as GenerateResponse | RefineResponse;
      const text = "justification" in result ? result.justification : result.summary;
      setTurns((prev) => [...prev, { role: "assistant", text, result }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [input, currentPattern, sessionId]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        void submit();
      }
    },
    [submit],
  );

  const lastAssistantTurn = [...turns].reverse().find((t) => t.role === "assistant") as
    | (Turn & { role: "assistant" })
    | undefined;

  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(320px, 420px) 1fr",
        gap: "1rem",
        flex: 1,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          background: "var(--bg-2)",
          borderRadius: 8,
          border: "1px solid var(--border)",
          minHeight: "60vh",
        }}
      >
        <div style={{ flex: 1, overflowY: "auto", padding: "0.75rem" }}>
          {turns.length === 0 && (
            <p style={{ color: "var(--fg-muted)" }}>
              Try: <em>"hub-spoke landing zone with AKS workload and Azure SQL MI"</em>
            </p>
          )}
          {turns.map((t, i) => (
            <div
              // biome-ignore lint/suspicious/noArrayIndexKey: turns are append-only
              key={i}
              style={{
                marginBottom: "0.5rem",
                padding: "0.5rem 0.75rem",
                borderRadius: 6,
                background: t.role === "user" ? "var(--bg-3)" : "transparent",
                borderLeft: t.role === "assistant" ? "3px solid var(--accent)" : "none",
              }}
            >
              <div style={{ fontSize: "0.75rem", color: "var(--fg-muted)" }}>
                {t.role === "user" ? "you" : "architect"}
              </div>
              <div>{t.text}</div>
              {t.role === "assistant" && "candidate_pattern_names" in t.result && (
                <div
                  style={{ fontSize: "0.75rem", color: "var(--fg-muted)", marginTop: "0.25rem" }}
                >
                  considered: {t.result.candidate_pattern_names.join(", ")}
                </div>
              )}
              {t.role === "assistant" && (
                <div style={{ fontSize: "0.7rem", color: "var(--fg-muted)", marginTop: "0.25rem" }}>
                  tokens: {t.result.tokens_input}in / {t.result.tokens_output}out
                </div>
              )}
            </div>
          ))}
          {error && <div style={{ color: "var(--error)", padding: "0.5rem 0" }}>{error}</div>}
        </div>
        <div
          style={{
            borderTop: "1px solid var(--border)",
            padding: "0.75rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem",
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              currentPattern
                ? "Refine — e.g. add a private endpoint to SQL"
                : "Describe your Azure workload…"
            }
            rows={3}
            disabled={busy}
          />
          <button type="button" onClick={() => void submit()} disabled={busy || !input.trim()}>
            {busy ? "thinking…" : currentPattern ? "refine" : "generate"}
          </button>
        </div>
      </div>
      <div>
        {lastAssistantTurn ? (
          <DiagramView result={lastAssistantTurn.result} />
        ) : (
          <div
            style={{
              border: "1px dashed var(--border)",
              borderRadius: 8,
              padding: "2rem",
              color: "var(--fg-muted)",
              textAlign: "center",
            }}
          >
            Diagram will appear here.
          </div>
        )}
      </div>
    </section>
  );
}
