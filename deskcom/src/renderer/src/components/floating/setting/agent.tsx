import { useState, useEffect } from 'react';
import { Box, Field, Switch, Input, Select, createListCollection, Spinner, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useWebSocket } from '@/context/websocket-context';
import { useAgentSettings } from '@/hooks/floating/setting/use-agent-settings';
import { useAgentProviderConfig } from '@/context/agent-provider-config-context';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';

const fieldLabelStyles = {
  color: '#c0c0e0',
  fontSize: 'sm',
  mb: 1,
  fontWeight: 'medium',
};

const inputStyles = {
  bg: '#0f0f23',
  border: '1px solid',
  borderColor: '#2a2a4a',
  color: '#e0e0ff',
  _placeholder: { color: '#555577' },
  _focus: { borderColor: '#6666aa', outline: 'none', boxShadow: '0 0 0 1px #6666aa' },
  _hover: { borderColor: '#3a3a5a' },
  rounded: 'md',
  fontSize: 'sm',
};

const selectTriggerStyles = {
  bg: '#0f0f23',
  border: '1px solid',
  borderColor: '#2a2a4a',
  color: '#e0e0ff',
  _hover: { borderColor: '#3a3a5a' },
  _focus: { borderColor: '#6666aa' },
  rounded: 'md',
  fontSize: 'sm',
};

function Agent() {
  const { t } = useTranslation();
  const { sendMessage } = useWebSocket();
  const {
    allowProactiveSpeak, setAllowProactiveSpeak,
    idleSecondsToSpeak, setIdleSecondsToSpeak,
    allowButtonTrigger, setAllowButtonTrigger,
  } = useAgentSettings();
  const { agentConfig, setAvailableModels } = useAgentProviderConfig();
  const [fetchingModels, setFetchingModels] = useState(false);
  const [modelInput, setModelInput] = useState('');
  const [aiMode, setAiMode] = useLocalStorage('aiMode', 'full_agent');

  const aiModeOptions = createListCollection({
    items: [
      { label: 'Lite', value: 'lite' },
      { label: 'Minimal', value: 'minimal' },
      { label: 'Full Agent', value: 'full_agent' },
    ],
  });

  const providerOptions = createListCollection({
    items: (agentConfig?.available_providers || []).map((p) => ({
      label: p,
      value: p,
    })),
  });

  const availableModels = agentConfig?.available_models || [];
  const hasFetchedModels = availableModels.length > 0;

  const modelOptions = createListCollection({
    items: availableModels.map((m) => ({
      label: m,
      value: m,
    })),
  });

  useEffect(() => {
    setModelInput(agentConfig?.current_model || '');
  }, [agentConfig?.current_model]);

  const handleProviderChange = (value: string) => {
    setAvailableModels([]);
    setFetchingModels(true);
    sendMessage({
      type: 'save-config',
      llm_provider: value,
      model: agentConfig?.provider_models?.[value] || '',
    });
    sendMessage({
      type: 'fetch-available-models',
      provider: value,
    });
  };

  const handleModelSelect = (value: string) => {
    setModelInput(value);
    sendMessage({
      type: 'save-config',
      model: value,
    });
  };

  const commitModelInput = () => {
    const trimmed = modelInput.trim();
    if (trimmed && trimmed !== (agentConfig?.current_model || '')) {
      sendMessage({
        type: 'save-config',
        model: trimmed,
      });
    }
  };

  const handleModelKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitModelInput();
      (e.target as HTMLInputElement).blur();
    }
  };

  const handleAiModeChange = (value: string) => {
    setAiMode(value);
    sendMessage({ type: 'set-ai-mode', mode: value });
  };

  useEffect(() => {
    if (availableModels.length > 0) {
      setFetchingModels(false);
    }
  }, [availableModels]);

  useEffect(() => {
    if (agentConfig?.llm_provider) {
      setFetchingModels(true);
      setAvailableModels([]);
      sendMessage({
        type: 'fetch-available-models',
        provider: agentConfig.llm_provider,
      });
    }
  }, [agentConfig?.llm_provider]);

  return (
    <Box spaceY={5}>
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.agent.llmProvider')}</Field.Label>
        <Select.Root
          collection={providerOptions}
          value={agentConfig?.llm_provider ? [agentConfig.llm_provider] : []}
          onValueChange={(e) => handleProviderChange(e.value[0])}
        >
          <Select.HiddenSelect />
          <Select.Trigger css={selectTriggerStyles}>
            <Select.ValueText placeholder="Select provider..." />
          </Select.Trigger>
          <Select.Content>
            {providerOptions.items.map((opt) => (
              <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.agent.model')}</Field.Label>
        {fetchingModels ? (
          <Box display="flex" alignItems="center" gap={2} py={2}>
            <Spinner size="xs" color="#6666aa" />
            <Text fontSize="sm" color="#555577">Fetching models...</Text>
          </Box>
        ) : hasFetchedModels ? (
          <Box spaceY={2}>
            <Select.Root
              collection={modelOptions}
              value={agentConfig?.current_model ? [agentConfig.current_model] : []}
              onValueChange={(e) => handleModelSelect(e.value[0])}
            >
              <Select.HiddenSelect />
              <Select.Trigger css={selectTriggerStyles}>
                <Select.ValueText placeholder="Select model..." />
              </Select.Trigger>
              <Select.Content>
                {modelOptions.items.map((opt) => (
                  <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
            <Input
              value={modelInput}
              onChange={(e) => setModelInput(e.target.value)}
              onKeyDown={handleModelKeyDown}
              onBlur={commitModelInput}
              placeholder="Or type custom model ID and press Enter..."
              css={inputStyles}
              fontSize="xs"
            />
          </Box>
        ) : (
          <Input
            value={modelInput}
            onChange={(e) => setModelInput(e.target.value)}
            onKeyDown={handleModelKeyDown}
            onBlur={commitModelInput}
            placeholder="Type model name and press Enter..."
            css={inputStyles}
          />
        )}
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>AI Mode</Field.Label>
        <Select.Root
          collection={aiModeOptions}
          value={[aiMode]}
          onValueChange={(e) => handleAiModeChange(e.value[0])}
        >
          <Select.HiddenSelect />
          <Select.Trigger css={selectTriggerStyles}>
            <Select.ValueText placeholder="Select AI mode..." />
          </Select.Trigger>
          <Select.Content>
            {aiModeOptions.items.map((opt) => (
              <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.agent.allowProactiveSpeak')}</Field.Label>
        <Switch.Root checked={allowProactiveSpeak} onCheckedChange={(e) => setAllowProactiveSpeak(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      {allowProactiveSpeak && (
        <Field.Root>
          <Field.Label css={fieldLabelStyles}>{t('settings.agent.idleSecondsToSpeak')}</Field.Label>
          <Input
            type="number"
            step={0.1}
            value={idleSecondsToSpeak}
            onChange={(e) => setIdleSecondsToSpeak(parseFloat(e.target.value))}
            css={inputStyles}
          />
        </Field.Root>
      )}

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.agent.allowButtonTrigger')}</Field.Label>
        <Switch.Root checked={allowButtonTrigger} onCheckedChange={(e) => setAllowButtonTrigger(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>
    </Box>
  );
}

export default Agent;
