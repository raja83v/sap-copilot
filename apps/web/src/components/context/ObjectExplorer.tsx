/**
 * ObjectExplorer — shows SAP package/object tree.
 * Will be populated from SearchObject / GetPackage tool results.
 */
export function ObjectExplorer() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 32,
        color: "var(--sapContent_LabelColor)",
        textAlign: "center",
        gap: 12,
      }}
    >
      <span style={{ fontSize: 32 }}>🌲</span>
      <div style={{ fontSize: 13 }}>
        SAP object tree will appear here when you browse packages or search objects.
      </div>
    </div>
  );
}
