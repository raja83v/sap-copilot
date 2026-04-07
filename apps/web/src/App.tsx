import { Routes, Route, Navigate } from "react-router-dom";
import { ShellLayout } from "./components/layout/ShellLayout";
import { ConvexProvider, ConvexReactClient } from "convex/react";

const convex = new ConvexReactClient(
  import.meta.env.VITE_CONVEX_URL ?? "http://localhost:3210"
);

export function App() {
  return (
    <ConvexProvider client={convex}>
      <Routes>
        {/* All routes rendered inside the shell */}
        <Route path="/*" element={<ShellLayout />} />
        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ConvexProvider>
  );
}
