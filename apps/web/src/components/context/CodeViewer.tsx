import { useState } from "react";

/**
 * CodeViewer — displays ABAP source code fetched from tool calls.
 * Will be wired to receive source from GetSource / GetClassInclude results.
 */
export function CodeViewer() {
  const [source] = useState<string | null>(null);
  const [objectName] = useState<string>("No code loaded");

  if (!source) {
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
        <span style={{ fontSize: 32 }}>📝</span>
        <div style={{ fontSize: 13 }}>
          Source code will appear here when you ask to view an ABAP object.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* File header */}
      <div
        style={{
          padding: "6px 12px",
          background: "var(--sapList_HeaderBackground)",
          borderBottom: "1px solid var(--sapGroup_ContentBorderColor)",
          fontSize: 12,
          fontWeight: 600,
          fontFamily: "'72Mono', monospace",
          color: "var(--sapTextColor)",
        }}
      >
        {objectName}
      </div>

      {/* Code area */}
      <div style={{ flex: 1, overflow: "auto" }}>
        <pre
          style={{
            fontFamily: "'72Mono', 'Fira Code', 'Consolas', monospace",
            fontSize: 12,
            lineHeight: 1.6,
            padding: 12,
            margin: 0,
            whiteSpace: "pre",
            tabSize: 2,
            color: "var(--sapTextColor)",
          }}
        >
          {source}
        </pre>
      </div>
    </div>
  );
}
