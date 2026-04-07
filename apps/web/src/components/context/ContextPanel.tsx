import {
  Button,
  IllustratedMessage,
  Icon,
} from "@ui5/webcomponents-react";
import "@ui5/webcomponents-fiori/dist/illustrations/NoData.js";
import "@ui5/webcomponents-fiori/dist/illustrations/SimpleBalloon.js";
import { useAppStore } from "@/stores/appStore";
import { CodeViewer } from "./CodeViewer";
import { ObjectExplorer } from "./ObjectExplorer";

export function ContextPanel() {
  const { contextPanelTab, setContextPanelTab, toggleContextPanel } = useAppStore();
  const tabs = [
    { id: "code", label: "Code", icon: "source-code" },
    { id: "explorer", label: "Explorer", icon: "tree" },
    { id: "details", label: "Details", icon: "detail-view" },
    { id: "history", label: "History", icon: "history" },
  ] as const;

  return (
    <div className="context-panel-shell">
      <div className="context-panel__header">
        <div>
          <div className="context-panel__eyebrow">Workspace context</div>
          <div className="context-panel__title">Context</div>
        </div>
        <Button
          icon="decline"
          design="Transparent"
          onClick={toggleContextPanel}
          tooltip="Close panel"
        />
      </div>

      <div className="context-panel__tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`context-panel__tab ${contextPanelTab === tab.id ? "context-panel__tab--active" : ""}`}
            onClick={() => setContextPanelTab(tab.id)}
          >
            <Icon name={tab.icon} style={{ fontSize: 14 }} />
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="context-panel__body sap-scroll">
        {contextPanelTab === "code" && <CodeViewer />}
        {contextPanelTab === "explorer" && <ObjectExplorer />}
        {contextPanelTab === "details" && <DetailsTab />}
        {contextPanelTab === "history" && <HistoryTab />}
      </div>
    </div>
  );
}

function DetailsTab() {
  return (
    <div className="context-panel__empty-state">
      <IllustratedMessage
        name="NoData"
        titleText="No object selected"
        subtitleText="Click on an object in chat or explorer to see details"
      />
    </div>
  );
}

function HistoryTab() {
  return (
    <div className="context-panel__empty-state">
      <IllustratedMessage
        name="NoData"
        titleText="No history yet"
        subtitleText="Tool calls and operations will appear here"
      />
    </div>
  );
}
