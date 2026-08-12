import { Box } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Text } from '@chakra-ui/react';
import SchemaForm from './schema-form';

function Advanced() {
  const { t } = useTranslation();
  return (
    <Box spaceY={5}>
      <Text fontSize="xs" color="var(--sk-ink-faint)">
        {t('settings.advancedHint')}
      </Text>
      <SchemaForm rootPath="character_config.agent_config" />
      <SchemaForm rootPath="character_config.tts_preprocessor_config" />
    </Box>
  );
}

export default Advanced;
