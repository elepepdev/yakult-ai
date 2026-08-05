import { Box, Field, Select, Switch, Input, createListCollection } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useGeneralSettings } from '@/hooks/floating/setting/use-general-settings';

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

function General() {
  const { t, i18n } = useTranslation();
  const {
    language,
    setLanguage,
    showSubtitle,
    setShowSubtitle,
    useCameraBg,
    setUseCameraBg,
    confName,
    configFiles,
    setConfName,
    wsUrl,
    setWsUrl,
    baseUrl,
    setBaseUrl,
    imageCompressionQuality,
    setImageCompressionQuality,
    imageMaxWidth,
    setImageMaxWidth,
    gridSpec,
    setGridSpec,
  } = useGeneralSettings();

  const languageOptions = createListCollection({
    items: [
      { label: 'English', value: 'en' },
      { label: 'Chinese', value: 'zh' },
    ],
  });

  const characterOptions = createListCollection({
    items: (configFiles || []).map((f: any) => ({
      label: f.name || f.filename,
      value: f.filename,
    })),
  });

  return (
    <Box spaceY={5}>
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.language')}</Field.Label>
        <Select.Root
          collection={languageOptions}
          value={[language]}
          onValueChange={(e) => {
            setLanguage(e.value[0]);
            i18n.changeLanguage(e.value[0]);
          }}
        >
          <Select.Trigger css={selectTriggerStyles}>
            <Select.ValueText />
          </Select.Trigger>
          <Select.Content>
            {languageOptions.items.map((opt) => (
              <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.showSubtitle')}</Field.Label>
        <Switch.Root
          checked={showSubtitle}
          onCheckedChange={(e) => setShowSubtitle(e.checked)}
          colorScheme="blue"
        >
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.useCameraBackground')}</Field.Label>
        <Switch.Root
          checked={useCameraBg}
          onCheckedChange={(e) => setUseCameraBg(e.checked)}
          colorScheme="blue"
        >
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.characterPreset')}</Field.Label>
        <Select.Root
          collection={characterOptions}
          value={[confName]}
          onValueChange={(e) => setConfName(e.value[0])}
        >
          <Select.Trigger css={selectTriggerStyles}>
            <Select.ValueText />
          </Select.Trigger>
          <Select.Content>
            {characterOptions.items.map((opt) => (
              <Select.Item item={opt} key={opt.value}>{opt.label}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.wsUrl')}</Field.Label>
        <Input
          value={wsUrl}
          onChange={(e) => setWsUrl(e.target.value)}
          placeholder="ws://localhost:12393"
          css={inputStyles}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.baseUrl')}</Field.Label>
        <Input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="http://localhost:12393"
          css={inputStyles}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.imageCompressionQuality')}</Field.Label>
        <Input
          type="number"
          min={0.1}
          max={1.0}
          step={0.1}
          value={imageCompressionQuality}
          onChange={(e) => setImageCompressionQuality(parseFloat(e.target.value))}
          css={inputStyles}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.imageMaxWidth')}</Field.Label>
        <Input
          type="number"
          min={0}
          value={imageMaxWidth}
          onChange={(e) => setImageMaxWidth(parseInt(e.target.value, 10))}
          css={inputStyles}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.general.gridResolution')}</Field.Label>
        <Select.Root
          collection={createListCollection({
            items: [
              { label: '6 × 4 (coarse)', value: '6x4' },
              { label: '8 × 6 (default)', value: '8x6' },
              { label: '10 × 8', value: '10x8' },
              { label: '12 × 9', value: '12x9' },
              { label: '14 × 10', value: '14x10' },
              { label: '16 × 12 (fine)', value: '16x12' },
              { label: '20 × 15 (finest)', value: '20x15' },
            ],
          })}
          value={[gridSpec]}
          onValueChange={(e) => setGridSpec(e.value[0])}
        >
          <Select.Trigger css={selectTriggerStyles}>
            <Select.ValueText />
          </Select.Trigger>
          <Select.Content>
            {['6x4', '8x6', '10x8', '12x9', '14x10', '16x12', '20x15'].map((opt) => (
              <Select.Item item={{ label: opt, value: opt }} key={opt}>{opt}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Field.Root>
    </Box>
  );
}

export default General;
