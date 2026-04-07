import { useState, useEffect } from "react";
import {
  Dialog,
  Bar,
  Button,
  Input,
  Label,
  MessageStrip,
  FlexBox,
  BusyIndicator,
} from "@ui5/webcomponents-react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../../../../convex/_generated/api";
import { configureLiteLLM, listLLMModels } from "@/lib/gateway";
import { useAppStore } from "@/stores/appStore";

interface LLMConfigDialogProps {
  open: boolean;
  onClose: () => void;
}

export function LLMConfigDialog({ open, onClose }: LLMConfigDialogProps) {
  const config = useQuery(api.llmConfig.get);
  const upsertConfig = useMutation(api.llmConfig.upsert);
  const refreshModels = useAppStore((state) => state.refreshModels);

  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // Seed form from Convex when loaded
  useEffect(() => {
    if (config) {
      setBaseUrl(config.baseUrl);
      setApiKey(config.apiKey);
    }
  }, [config]);

  const handleSave = async () => {
    if (!baseUrl.trim()) return;
    setSaving(true);
    setStatus(null);
    try {
      // Persist to Convex
      await upsertConfig({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() });
      // Push to gateway
      await configureLiteLLM({ base_url: baseUrl.trim(), api_key: apiKey.trim() });
      setStatus({ type: "success", msg: "LiteLLM proxy configured and synced to gateway." });
      refreshModels();
    } catch (e) {
      setStatus({ type: "error", msg: `Save failed: ${e instanceof Error ? e.message : e}` });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setStatus(null);
    try {
      // First push config to gateway, then try to list models
      await configureLiteLLM({ base_url: baseUrl.trim(), api_key: apiKey.trim() });
      const models = await listLLMModels();
      if (models.length > 0) {
        setStatus({ type: "success", msg: `Connected! Found ${models.length} model(s).` });
        refreshModels();
      } else {
        setStatus({ type: "error", msg: "Connected but no models returned. Check your LiteLLM config." });
      }
    } catch (e) {
      setStatus({ type: "error", msg: `Cannot reach LiteLLM proxy: ${e instanceof Error ? e.message : e}` });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Dialog
      open={open}
      headerText="LiteLLM Configuration"
      onClose={onClose}
      footer={
        <Bar
          design="Footer"
          endContent={
            <FlexBox style={{ gap: 8 }}>
              <Button design="Default" onClick={handleTestConnection} disabled={testing || !baseUrl.trim()}>
                {testing ? "Testing..." : "Test Connection"}
              </Button>
              <Button design="Emphasized" onClick={handleSave} disabled={saving || !baseUrl.trim()}>
                {saving ? "Saving..." : "Save"}
              </Button>
              <Button design="Transparent" onClick={onClose}>
                Close
              </Button>
            </FlexBox>
          }
        />
      }
      style={{ width: 520 }}
    >
      <div className="settings-dialog-shell">
        <MessageStrip design="Information" hideCloseButton>
          Enter the URL and API key of your LiteLLM proxy server. Models configured in
          LiteLLM will automatically appear in the chat model selector.
        </MessageStrip>

        {status && (
          <MessageStrip
            design={status.type === "success" ? "Positive" : "Negative"}
            onClose={() => setStatus(null)}
          >
            {status.msg}
          </MessageStrip>
        )}

        <div className="settings-dialog-field">
          <Label className="settings-dialog-field__label" style={{ marginBottom: 4, display: "block" }} required>
            LiteLLM Base URL
          </Label>
          <Input
            value={baseUrl}
            placeholder="http://localhost:4000"
            onInput={(e) => setBaseUrl((e.target as unknown as HTMLInputElement).value)}
            style={{ width: "100%" }}
          />
          <div className="settings-dialog-field__hint">
            The URL where your LiteLLM proxy is running (e.g. http://localhost:4000)
          </div>
        </div>

        <div className="settings-dialog-field">
          <Label className="settings-dialog-field__label" style={{ marginBottom: 4, display: "block" }}>
            API Key
          </Label>
          <Input
            type="Password"
            value={apiKey}
            placeholder="sk-1234"
            onInput={(e) => setApiKey((e.target as unknown as HTMLInputElement).value)}
            style={{ width: "100%" }}
          />
          <div className="settings-dialog-field__hint">
            The master/virtual key for authenticating with the LiteLLM proxy
          </div>
        </div>

        {(saving || testing) && (
          <FlexBox alignItems="Center" className="settings-dialog-status-row">
            <BusyIndicator active size="S" />
            <span className="settings-dialog-field__hint">
              {testing ? "Connecting to LiteLLM proxy..." : "Saving configuration..."}
            </span>
          </FlexBox>
        )}
      </div>
    </Dialog>
  );
}
