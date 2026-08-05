import { createContext, useContext, useState, useMemo, ReactNode } from 'react';

interface AgentConfigData {
  llm_provider: string;
  current_model: string;
  available_providers: string[];
  provider_models: Record<string, string>;
  available_models?: string[];
}

interface AgentProviderConfigState {
  agentConfig: AgentConfigData | null;
  setAgentConfig: (config: AgentConfigData) => void;
  setAvailableModels: (models: string[]) => void;
}

const defaultState: AgentProviderConfigState = {
  agentConfig: null,
  setAgentConfig: () => {},
  setAvailableModels: () => {},
};

export const AgentProviderConfigContext = createContext<AgentProviderConfigState>(defaultState);

export function AgentProviderConfigProvider({ children }: { children: ReactNode }) {
  const [agentConfig, setAgentConfig] = useState<AgentConfigData | null>(null);

  const setAvailableModels = (models: string[]) => {
    setAgentConfig((prev) =>
      prev ? { ...prev, available_models: models } : prev,
    );
  };

  const value = useMemo(
    () => ({ agentConfig, setAgentConfig, setAvailableModels }),
    [agentConfig],
  );

  return (
    <AgentProviderConfigContext.Provider value={value}>
      {children}
    </AgentProviderConfigContext.Provider>
  );
}

export function useAgentProviderConfig() {
  const context = useContext(AgentProviderConfigContext);
  if (!context) {
    throw new Error('useAgentProviderConfig must be used within AgentProviderConfigProvider');
  }
  return context;
}
