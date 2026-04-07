import { createRoot } from "react-dom/client";
import { ThemeProvider } from "@ui5/webcomponents-react";
import "@ui5/webcomponents-react/dist/Assets.js";
import "@ui5/webcomponents-icons/dist/AllIcons.js";
import { setTheme } from "@ui5/webcomponents-base/dist/config/Theme.js";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles/global.css";

// Default to SAP Horizon Light for corporate use; persisted preference applied by App
const stored = localStorage.getItem("sap_copilot_theme") ?? "sap_horizon";
setTheme(stored);

const root = document.getElementById("root")!;
createRoot(root).render(
  <BrowserRouter>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </BrowserRouter>
);
