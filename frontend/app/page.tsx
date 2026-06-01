import { Chat } from "./components/Chat";
import { Footer } from "./components/Footer";

export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        maxWidth: "1400px",
        margin: "0 auto",
        padding: "1.5rem",
      }}
    >
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ margin: 0, fontSize: "1.75rem" }}>Genesis</h1>
        <p style={{ margin: "0.25rem 0", color: "var(--fg-muted)" }}>
          Describe your Azure workload — we'll match it to a reference architecture and generate the
          diagram.
        </p>
      </header>
      <Chat />
      <Footer />
    </main>
  );
}
