export function Footer() {
  return (
    <footer
      style={{
        marginTop: "auto",
        paddingTop: "2rem",
        paddingBottom: "1rem",
        borderTop: "1px solid var(--border)",
        color: "var(--fg-muted)",
        fontSize: "0.85rem",
        textAlign: "center",
      }}
    >
      <p style={{ margin: "0.5rem 0" }}>
        Azure service icons © Microsoft, used under the{" "}
        <a
          href="https://learn.microsoft.com/azure/architecture/icons/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Microsoft Azure Architecture Icons Terms of Use
        </a>
        .
      </p>
      <p style={{ margin: "0.5rem 0" }}>
        Source:{" "}
        <a
          href="https://github.com/mprawironego_microsoft/Genesis-DiagramArchitectureGenerator"
          target="_blank"
          rel="noopener noreferrer"
        >
          mprawironego_microsoft/Genesis-DiagramArchitectureGenerator
        </a>
        {" · MIT licensed."}
      </p>
    </footer>
  );
}
