import { useQuery } from "convex/react";
import { useEffect, useState } from "react";
import { api } from "../../../../convex/_generated/api";
import { configureLiteLLM, listLLMModels, type LLMModel } from "@/lib/gateway";
import { useAppStore } from "@/stores/appStore";

/**
 * Watches Convex llmConfig, syncs to gateway, and returns available models from LiteLLM proxy.
 * Also reacts to `modelRefreshKey` so other components (e.g. LLMConfigDialog) can trigger a refetch.
 */
export function useLLMModels() {
  const config = useQuery(api.llmConfig.get);
  const [models, setModels] = useState<LLMModel[]>([]);
  const { selectedModel, setSelectedModel, modelRefreshKey } = useAppStore();

  // Sync config to gateway and fetch models whenever config changes or refresh is triggered
  useEffect(() => {
    if (!config || !config.baseUrl) return;
    let cancelled = false;

    (async () => {
      try {
        await configureLiteLLM({ base_url: config.baseUrl, api_key: config.apiKey });
      } catch {
        // Gateway may not be running
      }

      try {
        const fetched = await listLLMModels();
        if (!cancelled && fetched.length > 0) {
          setModels(fetched);
        }
      } catch {
        // LiteLLM proxy may be unreachable
      }
    })();

    return () => { cancelled = true; };
  }, [config?.baseUrl, config?.apiKey, modelRefreshKey]);

  // Auto-select first model if none selected or current selection invalid
  useEffect(() => {
    if (models.length > 0 && (!selectedModel || !models.some((m) => m.id === selectedModel))) {
      setSelectedModel(models[0].id);
    }
  }, [models, selectedModel, setSelectedModel]);

  return models;
}
