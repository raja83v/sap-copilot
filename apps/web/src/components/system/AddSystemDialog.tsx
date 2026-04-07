import { useState } from "react";
import {
  Dialog,
  Bar,
  Button,
  Input,
  Label,
  Select,
  Option,
  MessageStrip,
  FlexBox,
  Title,
} from "@ui5/webcomponents-react";
import { SYSTEM_COLORS } from "@sap-copilot/shared";
import { testSystemConnection } from "@/lib/gateway";

interface AddSystemDialogProps {
  open: boolean;
  onClose: () => void;
  onAdd: (system: SystemFormData) => void;
}

export interface SystemFormData {
  name: string;
  url: string;
  client: string;
  user: string;
  password: string;
  language: string;
  proxy?: string;
  color: string;
  description: string;
}

const INITIAL_FORM: SystemFormData = {
  name: "",
  url: "",
  client: "100",
  user: "",
  password: "",
  language: "EN",
  proxy: "",
  color: SYSTEM_COLORS[0],
  description: "",
};

export function AddSystemDialog({ open, onClose, onAdd }: AddSystemDialogProps) {
  const [form, setForm] = useState<SystemFormData>({ ...INITIAL_FORM });
  const [errors, setErrors] = useState<Partial<Record<keyof SystemFormData, string>>>({});
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const update = <K extends keyof SystemFormData>(field: K, value: SystemFormData[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.name.trim()) errs.name = "Name is required";
    if (!form.url.trim()) errs.url = "URL is required";
    else if (!/^https?:\/\/.+/.test(form.url)) errs.url = "Must be a valid HTTP(S) URL";
    if (!form.client.trim()) errs.client = "Client is required";
    else if (!/^\d{3}$/.test(form.client)) errs.client = "Must be 3 digits";
    if (!form.user.trim()) errs.user = "User is required";
    if (!form.password.trim()) errs.password = "Password is required";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleAdd = () => {
    if (!validate()) return;
    onAdd(form);
    setForm({ ...INITIAL_FORM });
    onClose();
  };

  const handleTestConnection = async () => {
    if (!validate()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testSystemConnection({
        system_id: `test_${Date.now()}`,
        url: form.url,
        user: form.user,
        password: form.password,
        client: form.client,
        language: form.language,
        proxy: form.proxy || undefined,
      });
      if (result.status === "success") {
        setTestResult({
          success: true,
          message: `Connection successful! ${result.tools_count} tools available.`,
        });
      } else {
        setTestResult({
          success: false,
          message: result.detail || "Connection failed.",
        });
      }
    } catch (e) {
      setTestResult({
        success: false,
        message: `Could not reach gateway: ${(e as Error).message}`,
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Dialog
      open={open}
      headerText="Add SAP System"
      onClose={onClose}
      footer={
        <Bar
          design="Footer"
          endContent={
            <FlexBox style={{ gap: 8 }}>
              <Button design="Transparent" onClick={onClose}>
                Cancel
              </Button>
              <Button design="Default" onClick={handleTestConnection} disabled={testing}>
                {testing ? "Testing..." : "Test Connection"}
              </Button>
              <Button design="Emphasized" onClick={handleAdd}>
                Add System
              </Button>
            </FlexBox>
          }
        />
      }
      style={{ width: 520 }}
    >
      <div className="settings-dialog-shell">
        <MessageStrip design="Information" hideCloseButton>
          Credentials are encrypted with AES-256-GCM before storage.
        </MessageStrip>

        {testResult && (
          <MessageStrip
            design={testResult.success ? "Positive" : "Negative"}
            onClose={() => setTestResult(null)}
          >
            {testResult.message}
          </MessageStrip>
        )}

        {/* System Identity */}
        <Title level="H6" className="settings-dialog-section-title">System Identity</Title>
        <FormField label="System Name" error={errors.name} required>
          <Input
            value={form.name}
            placeholder="e.g., DEV, QAS, PRD"
            onInput={(e) => update("name", (e.target as unknown as HTMLInputElement).value)}
            valueState={errors.name ? "Negative" : "None"}
            style={{ width: "100%" }}
          />
        </FormField>

        <FormField label="Description">
          <Input
            value={form.description}
            placeholder="Optional system description"
            onInput={(e) => update("description", (e.target as unknown as HTMLInputElement).value)}
            style={{ width: "100%" }}
          />
        </FormField>

        <FlexBox style={{ gap: 12 }}>
          <div style={{ flex: 1 }}>
            <FormField label="Color">
              <FlexBox className="settings-color-grid">
                {SYSTEM_COLORS.map((c) => (
                  <div
                    key={c}
                    onClick={() => update("color", c)}
                    className={`settings-color-swatch ${form.color === c ? "settings-color-swatch--active" : ""}`}
                    style={{ background: c }}
                  />
                ))}
              </FlexBox>
            </FormField>
          </div>
        </FlexBox>

        {/* Connection */}
        <Title level="H6" className="settings-dialog-section-title">Connection</Title>
        <FormField label="Server URL" error={errors.url} required>
          <Input
            value={form.url}
            placeholder="https://sap.example.com:8000"
            onInput={(e) => update("url", (e.target as unknown as HTMLInputElement).value)}
            valueState={errors.url ? "Negative" : "None"}
            style={{ width: "100%" }}
          />
        </FormField>

        <FlexBox style={{ gap: 12 }}>
          <div style={{ flex: 1 }}>
            <FormField label="Client" error={errors.client} required>
              <Input
                value={form.client}
                placeholder="100"
                maxlength={3}
                onInput={(e) => update("client", (e.target as unknown as HTMLInputElement).value)}
                valueState={errors.client ? "Negative" : "None"}
                style={{ width: "100%" }}
              />
            </FormField>
          </div>
          <div style={{ flex: 1 }}>
            <FormField label="Language">
              <Select
                style={{ width: "100%" }}
                onChange={(e) => {
                  const val = (e.detail?.selectedOption as HTMLElement)?.textContent;
                  if (val) update("language", val);
                }}
              >
                <Option selected={form.language === "EN"}>EN</Option>
                <Option selected={form.language === "DE"}>DE</Option>
                <Option selected={form.language === "JA"}>JA</Option>
                <Option selected={form.language === "ZH"}>ZH</Option>
              </Select>
            </FormField>
          </div>
        </FlexBox>

        {/* Credentials */}
        <Title level="H6" className="settings-dialog-section-title">Credentials</Title>
        <FormField label="Username" error={errors.user} required>
          <Input
            value={form.user}
            placeholder="SAP username"
            onInput={(e) => update("user", (e.target as unknown as HTMLInputElement).value)}
            valueState={errors.user ? "Negative" : "None"}
            style={{ width: "100%" }}
          />
        </FormField>

        <FormField label="Password" error={errors.password} required>
          <Input
            value={form.password}
            type="Password"
            placeholder="SAP password"
            onInput={(e) => update("password", (e.target as unknown as HTMLInputElement).value)}
            valueState={errors.password ? "Negative" : "None"}
            style={{ width: "100%" }}
          />
        </FormField>

        {/* Advanced */}
        <Title level="H6" className="settings-dialog-section-title">Advanced</Title>
        <FormField label="HTTP Proxy">
          <Input
            value={form.proxy ?? ""}
            placeholder="http://proxy.example.com:8080"
            onInput={(e) => update("proxy", (e.target as unknown as HTMLInputElement).value)}
            style={{ width: "100%" }}
          />
        </FormField>
      </div>
    </Dialog>
  );
}

function FormField({
  label,
  error,
  required,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="settings-dialog-field">
      <Label required={required} className="settings-dialog-field__label" style={{ marginBottom: 4, display: "block" }}>
        {label}
      </Label>
      {children}
      {error && (
        <div className="settings-dialog-field__error">
          {error}
        </div>
      )}
    </div>
  );
}
