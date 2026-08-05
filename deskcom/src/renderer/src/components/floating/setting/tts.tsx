import { Box, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';

function TTS() {
  const { t } = useTranslation();
  return (
    <Box p={4} bg="#0f0f23" rounded="md" border="1px solid" borderColor="#2a2a4a">
      <Text color="#8888bb" fontSize="sm">{t('settings.ttsPlaceholder')}</Text>
    </Box>
  );
}

export default TTS;
