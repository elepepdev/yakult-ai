import { useState, useEffect, useMemo } from 'react';
import { Box, Field, Select, Input, Spinner, Text, createListCollection } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import SchemaForm from './schema-form';
import { useConfigSchema } from '@/context/config-schema-context';
import { useWebSocket } from '@/context/websocket-context';
import { wsService } from '@/services/websocket-service';

const fieldLabelStyles = {
  color: 'var(--sk-ink-soft)',
  fontSize: 'sm',
  mb: 1,
  fontWeight: 'medium',
};

const inputStyles = {
  bg: 'var(--sk-paper-raised)',
  border: '1px solid',
  borderColor: 'var(--sk-outline)',
  color: 'var(--sk-ink)',
  _placeholder: { color: 'var(--sk-ink-mute)' },
  _focus: { borderColor: 'var(--sk-pencil-deep)', outline: 'none', boxShadow: '0 0 0 1px var(--sk-pencil-deep)' },
  _hover: { borderColor: 'var(--sk-outline-soft)' },
  rounded: 'md',
  fontSize: 'sm',
};

const selectTriggerStyles = {
  bg: 'var(--sk-paper-raised)',
  border: '1px solid',
  borderColor: 'var(--sk-outline)',
  color: 'var(--sk-ink)',
  _hover: { borderColor: 'var(--sk-outline-soft)' },
  _focus: { borderColor: 'var(--sk-pencil-deep)' },
  rounded: 'md',
  fontSize: 'sm',
};

function findNodeByPath(node: any, path: string): any {
  if (!node) return null;
  if (node.path === path) return node;
  for (const child of node.children || []) {
    const found = findNodeByPath(child, path);
    if (found) return found;
  }
  return null;
}

function TTS() {
  const { t } = useTranslation();
  const { schema } = useConfigSchema();
  const { sendMessage } = useWebSocket();

  const ttsModel = findNodeByPath(schema, 'character_config.tts_config.tts_model')?.value as string | undefined;

  const [voices, setVoices] = useState<string[]>([]);
  const [voiceField, setVoiceField] = useState('voice');
  const [voiceInput, setVoiceInput] = useState('');
  const [fetchingVoices, setFetchingVoices] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);

  const currentVoicePath = ttsModel
    ? `character_config.tts_config.${ttsModel}.${voiceField}`
    : '';
  const currentVoice = currentVoicePath
    ? findNodeByPath(schema, currentVoicePath)?.value
    : undefined;

  useEffect(() => {
    if (ttsModel) {
      setVoiceInput(currentVoice ?? '');
    }
  }, [currentVoice, ttsModel]);

  useEffect(() => {
    if (!ttsModel) return;
    setFetchingVoices(true);
    setHasFetched(false);
    setVoices([]);
    sendMessage({ type: 'fetch-available-voices', provider: ttsModel });
  }, [ttsModel, sendMessage]);

  useEffect(() => {
    const sub = wsService.onMessage((msg: any) => {
      if (msg.type === 'available-voices' && msg.provider === ttsModel) {
        setVoices(Array.isArray(msg.voices) ? msg.voices : []);
        if (msg.field) setVoiceField(msg.field);
        setFetchingVoices(false);
        setHasFetched(true);
      }
    });
    return () => sub.unsubscribe();
  }, [ttsModel]);

  const voiceOptions = useMemo(
    () => createListCollection({
      items: voices.map((v) => ({ label: v, value: v })),
    }),
    [voices],
  );

  const saveVoice = (value: string) => {
    const trimmed = value.trim();
    if (!ttsModel || !trimmed) return;
    setVoiceInput(trimmed);
    sendMessage({
      type: 'save-config-fields',
      updates: { [currentVoicePath]: trimmed },
    });
  };

  const handleVoiceKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveVoice(voiceInput);
      (e.target as HTMLInputElement).blur();
    }
  };

  return (
    <Box spaceY={5}>
      {ttsModel && (
        <Field.Root>
          <Field.Label css={fieldLabelStyles}>{t('settings.tts.voice')}</Field.Label>
          {fetchingVoices ? (
            <Box display="flex" alignItems="center" gap={2} py={2}>
              <Spinner size="xs" color="var(--sk-pencil-deep)" />
              <Text fontSize="sm" color="var(--sk-ink-mute)">{t('settings.tts.fetchingVoices')}</Text>
            </Box>
          ) : hasFetched && voices.length > 0 ? (
            <Box spaceY={2}>
              <Select.Root
                collection={voiceOptions}
                value={currentVoice ? [String(currentVoice)] : []}
                onValueChange={(e) => saveVoice(e.value[0])}
              >
                <Select.HiddenSelect />
                <Select.Trigger css={selectTriggerStyles}>
                  <Select.ValueText placeholder={t('settings.tts.selectVoice')} />
                </Select.Trigger>
                <Select.Content>
                  {voiceOptions.items.map((opt) => (
                    <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
              <Input
                value={voiceInput}
                onChange={(e) => setVoiceInput(e.target.value)}
                onKeyDown={handleVoiceKeyDown}
                onBlur={() => saveVoice(voiceInput)}
                placeholder={t('settings.tts.customVoice')}
                css={inputStyles}
                fontSize="xs"
              />
            </Box>
          ) : (
            <Input
              value={voiceInput}
              onChange={(e) => setVoiceInput(e.target.value)}
              onKeyDown={handleVoiceKeyDown}
              onBlur={() => saveVoice(voiceInput)}
              placeholder={t('settings.tts.voicePlaceholder')}
              css={inputStyles}
            />
          )}
          {!ttsModel && (
            <Text fontSize="xs" color="var(--sk-ink-mute)">{t('settings.tts.noProvider')}</Text>
          )}
        </Field.Root>
      )}
      <SchemaForm rootPath="character_config.tts_config" />
    </Box>
  );
}

export default TTS;
