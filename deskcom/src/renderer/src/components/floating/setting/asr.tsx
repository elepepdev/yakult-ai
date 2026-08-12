import { Box, Field, Switch, Input, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useASRSettings } from '@/hooks/floating/setting/use-asr-settings';
import SchemaForm from './schema-form';

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

function ASR() {
  const { t } = useTranslation();
  const {
    autoStopMic, setAutoStopMic,
    autoStartMicOn, setAutoStartMicOn,
    autoStartMicOnConvEnd, setAutoStartMicOnConvEnd,
    positiveSpeechThreshold, setPositiveSpeechThreshold,
    negativeSpeechThreshold, setNegativeSpeechThreshold,
    redemptionFrames, setRedemptionFrames,
  } = useASRSettings();

  return (
    <Box spaceY={5}>
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.asr.autoStopMic')}</Field.Label>
        <Switch.Root checked={autoStopMic} onCheckedChange={(e) => setAutoStopMic(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.asr.autoStartMicOn')}</Field.Label>
        <Switch.Root checked={autoStartMicOn} onCheckedChange={(e) => setAutoStartMicOn(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.asr.autoStartMicOnConvEnd')}</Field.Label>
        <Switch.Root checked={autoStartMicOnConvEnd} onCheckedChange={(e) => setAutoStartMicOnConvEnd(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.asr.positiveSpeechThreshold')}</Field.Label>
        <Input
          type="number"
          min={1}
          max={100}
          value={positiveSpeechThreshold}
          onChange={(e) => setPositiveSpeechThreshold(parseInt(e.target.value, 10))}
          css={inputStyles}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.asr.negativeSpeechThreshold')}</Field.Label>
        <Input
          type="number"
          min={0}
          max={100}
          value={negativeSpeechThreshold}
          onChange={(e) => setNegativeSpeechThreshold(parseInt(e.target.value, 10))}
          css={inputStyles}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.asr.redemptionFrames')}</Field.Label>
        <Input
          type="number"
          min={1}
          max={100}
          value={redemptionFrames}
          onChange={(e) => setRedemptionFrames(parseInt(e.target.value, 10))}
          css={inputStyles}
        />
      </Field.Root>

      <Box borderTop="1px solid" borderColor="var(--sk-outline)" />

      <Text fontSize="xs" fontWeight="semibold" color="var(--sk-ink-soft)">
        {t('settings.asr.backendConfig')}
      </Text>
      <SchemaForm rootPath="character_config.asr_config" />
    </Box>
  );
}

export default ASR;
