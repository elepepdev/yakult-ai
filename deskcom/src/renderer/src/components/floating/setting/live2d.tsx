import { useState, useMemo } from 'react';
import { Box, Field, Switch, Text, Flex, Badge, Button } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { LuUpload, LuUserCheck } from 'react-icons/lu';
import { useLive2dSettings } from '@/hooks/floating/setting/use-live2d-settings';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useConfig } from '@/context/character-config-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { VRMImportDialog } from '@/components/model/VRMImportDialog';

const fieldLabelStyles = {
  color: '#c0c0e0',
  fontSize: 'sm',
  mb: 1,
  fontWeight: 'medium',
};

function Live2D() {
  const { t } = useTranslation();
  const { pointerInteractive, setPointerInteractive, scrollToResize, setScrollToResize } = useLive2dSettings();
  const { modelInfo } = useLive2DConfig();
  const { configFiles } = useConfig();
  const { switchCharacter } = useSwitchCharacter();
  const [importOpen, setImportOpen] = useState(false);
  const modelType = modelInfo?.type || 'live2d';

  const vrmConfigs = useMemo(
    () => configFiles.filter((c) => c.filename.startsWith('vrm_')),
    [configFiles],
  );

  return (
    <Box spaceY={5}>
      {/* Model Type Info */}
      <Box
        p={3}
        rounded="md"
        bg="#0f0f23"
        border="1px solid"
        borderColor="#2a2a4a"
      >
        <Flex justify="space-between" align="center" mb={2}>
          <Text color="#8888bb" fontSize="xs" fontWeight="medium">Current Model Type</Text>
          <Badge
            colorScheme={modelType === 'vrm' ? 'purple' : 'blue'}
            fontSize="2xs"
            px={2}
            py={0.5}
            rounded="full"
          >
            {modelType === 'vrm' ? '3D VRM' : 'Live2D'}
          </Badge>
        </Flex>
        {modelInfo?.name && (
          <Text color="#c0c0e0" fontSize="sm" fontWeight="medium">
            {modelInfo.name}
          </Text>
        )}
      </Box>

      {/* VRM Import Button */}
      <Box
        p={3}
        rounded="md"
        bg="#0f0f23"
        border="1px dashed"
        borderColor="#3a3a6a"
        _hover={{ borderColor: '#5555aa' }}
        cursor="pointer"
        onClick={() => setImportOpen(true)}
      >
        <Flex align="center" gap={3}>
          <Box
            p={2}
            rounded="md"
            bg="#2a2a4a"
            color="#6666aa"
          >
            <LuUpload size={18} />
          </Box>
          <Box flex={1}>
            <Text color="#c0c0e0" fontSize="sm" fontWeight="medium">
              Import VRM Model
            </Text>
            <Text color="#666688" fontSize="xs">
              Drag & drop .vrm files or click to browse
            </Text>
          </Box>
        </Flex>
      </Box>

      {/* Previously imported VRM models */}
      {vrmConfigs.length > 0 && (
        <>
          <Box borderTop="1px solid" borderColor="#2a2a4a" />

          <Box
            p={3}
            rounded="md"
            bg="#0f0f23"
            border="1px solid"
            borderColor="#2a2a4a"
          >
            <Text color="#8888bb" fontSize="xs" fontWeight="medium" mb={3}>
              My VRM Models ({vrmConfigs.length})
            </Text>
            <Flex direction="column" gap={2}>
              {vrmConfigs.map((c) => (
                  <Button
                    key={c.filename}
                    size="sm"
                    variant="ghost"
                    justifyContent="flex-start"
                    px={3}
                    py={2}
                    h="auto"
                    bg={c.name === modelInfo?.name ? '#2a2a5a' : 'transparent'}
                    color={c.name === modelInfo?.name ? '#aaaaff' : '#8888bb'}
                    _hover={{ bg: '#2a2a4a', color: '#c0c0e0' }}
                    onClick={() => switchCharacter(c.filename)}
                  >
                    <Flex align="center" gap={2}>
                      <LuUserCheck size={14} />
                      {c.name}
                    </Flex>
                  </Button>
              ))}
            </Flex>
          </Box>
        </>
      )}

      {/* Divider */}
      <Box borderTop="1px solid" borderColor="#2a2a4a" />

      {/* Settings shared by both Live2D and VRM */}
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.live2d.scrollToResize')}</Field.Label>
        <Switch.Root checked={scrollToResize} onCheckedChange={(e) => setScrollToResize(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      {/* Live2D-only settings */}
      {modelType !== 'vrm' && (
        <>
          <Field.Root>
            <Field.Label css={fieldLabelStyles}>{t('settings.live2d.pointerInteractive')}</Field.Label>
            <Switch.Root checked={pointerInteractive} onCheckedChange={(e) => setPointerInteractive(e.checked)} colorScheme="blue">
              <Switch.HiddenInput />
              <Switch.Control />
            </Switch.Root>
          </Field.Root>
        </>
      )}

      {/* VRM Import Dialog */}
      <VRMImportDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </Box>
  );
}

export default Live2D;
