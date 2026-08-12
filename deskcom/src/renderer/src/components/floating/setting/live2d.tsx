import { useState, useMemo } from 'react';
import { Box, Field, Switch, Text, Flex, Badge, Button } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { LuUpload, LuUserCheck } from 'react-icons/lu';
import { useLive2dSettings } from '@/hooks/floating/setting/use-live2d-settings';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useConfig, ConfigFile } from '@/context/character-config-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { VRMImportDialog } from '@/components/model/VRMImportDialog';

const fieldLabelStyles = {
  color: 'var(--sk-ink-soft)',
  fontSize: 'sm',
  mb: 1,
  fontWeight: 'medium',
};

const TYPE_LABEL: Record<string, { text: string; color: string }> = {
  live2d: { text: 'Live2D', color: 'blue' },
  vrm: { text: '3D VRM', color: 'purple' },
  orb: { text: 'Orb', color: 'cyan' },
};

function CharacterGroup({
  title,
  items,
  currentName,
  onSwitch,
}: {
  title: string;
  items: ConfigFile[];
  currentName?: string;
  onSwitch: (filename: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <Box
      p={3}
      rounded="md"
      bg="var(--sk-paper-raised)"
      borderWidth="var(--sk-border)"
      borderColor="var(--sk-outline)"
    >
      <Text color="var(--sk-ink-faint)" fontSize="xs" fontWeight="medium" mb={3}>
        {title} ({items.length})
      </Text>
      <Flex direction="column" gap={2}>
        {items.map((c) => (
          <Button
            key={c.filename}
            size="sm"
            variant="ghost"
            justifyContent="flex-start"
            px={3}
            py={2}
            h="auto"
            bg={c.name === currentName ? 'var(--sk-outline-hover)' : 'transparent'}
            color={c.name === currentName ? 'var(--sk-pencil)' : 'var(--sk-ink-faint)'}
            _hover={{ bg: 'var(--sk-outline)', color: 'var(--sk-ink-soft)' }}
            onClick={() => onSwitch(c.filename)}
          >
            <Flex align="center" gap={2}>
              <LuUserCheck size={14} />
              {c.name}
            </Flex>
          </Button>
        ))}
      </Flex>
    </Box>
  );
}

function Live2D() {
  const { t } = useTranslation();
  const { pointerInteractive, setPointerInteractive, scrollToResize, setScrollToResize } = useLive2dSettings();
  const { modelInfo } = useLive2DConfig();
  const { configFiles } = useConfig();
  const { switchCharacter } = useSwitchCharacter();
  const [importOpen, setImportOpen] = useState(false);
  const modelType = modelInfo?.type || 'live2d';

  const groups = useMemo(() => {
    const live2d = configFiles.filter((c) => (c.model_type || 'live2d') === 'live2d');
    const vrm = configFiles.filter((c) => c.model_type === 'vrm');
    const orb = configFiles.filter((c) => c.model_type === 'orb');
    return { live2d, vrm, orb };
  }, [configFiles]);

  const typeBadge = TYPE_LABEL[modelType] || TYPE_LABEL.live2d;

  return (
    <Box spaceY={5}>
      {/* Model Type Info */}
      <Box
        p={3}
        rounded="md"
        bg="var(--sk-paper-raised)"
        borderWidth="var(--sk-border)"
        borderColor="var(--sk-outline)"
      >
        <Flex justify="space-between" align="center" mb={2}>
          <Text color="var(--sk-ink-faint)" fontSize="xs" fontWeight="medium">Current Model Type</Text>
          <Badge
            colorScheme={typeBadge.color}
            fontSize="2xs"
            px={2}
            py={0.5}
            rounded="full"
          >
            {typeBadge.text}
          </Badge>
        </Flex>
        {modelInfo?.name && (
          <Text color="var(--sk-ink-soft)" fontSize="sm" fontWeight="medium">
            {modelInfo.name}
          </Text>
        )}
      </Box>

      {/* VRM Import Button */}
      <Box
        p={3}
        rounded="md"
        bg="var(--sk-paper-raised)"
        border="1px dashed"
        borderColor="var(--sk-outline-soft)"
        _hover={{ borderColor: 'var(--sk-pencil-active)' }}
        cursor="pointer"
        onClick={() => setImportOpen(true)}
      >
        <Flex align="center" gap={3}>
          <Box
            p={2}
            rounded="md"
            bg="var(--sk-outline)"
            color="var(--sk-pencil-deep)"
          >
            <LuUpload size={18} />
          </Box>
          <Box flex={1}>
            <Text color="var(--sk-ink-soft)" fontSize="sm" fontWeight="medium">
              Import VRM Model
            </Text>
            <Text color="var(--sk-ink-dim)" fontSize="xs">
              Drag & drop .vrm files or click to browse
            </Text>
          </Box>
        </Flex>
      </Box>

      {/* Available characters grouped by type */}
      {(groups.live2d.length > 0 || groups.vrm.length > 0 || groups.orb.length > 0) && (
        <Box spaceY={3}>
          <Box borderTop="1px solid" borderColor="var(--sk-outline)" />
          <CharacterGroup
            title="Live2D Characters"
            items={groups.live2d}
            currentName={modelInfo?.name}
            onSwitch={switchCharacter}
          />
          <CharacterGroup
            title="Orb Characters"
            items={groups.orb}
            currentName={modelInfo?.name}
            onSwitch={switchCharacter}
          />
          <CharacterGroup
            title="My VRM Models"
            items={groups.vrm}
            currentName={modelInfo?.name}
            onSwitch={switchCharacter}
          />
        </Box>
      )}

      {/* Divider */}
      <Box borderTop="1px solid" borderColor="var(--sk-outline)" />

      {/* Settings shared by all model types */}
      <Field.Root>
        <Field.Label css={fieldLabelStyles}>{t('settings.live2d.scrollToResize')}</Field.Label>
        <Switch.Root checked={scrollToResize} onCheckedChange={(e) => setScrollToResize(e.checked)} colorScheme="blue">
          <Switch.HiddenInput />
          <Switch.Control />
        </Switch.Root>
      </Field.Root>

      {/* Live2D-only settings */}
      {modelType === 'live2d' && (
        <Field.Root>
          <Field.Label css={fieldLabelStyles}>{t('settings.live2d.pointerInteractive')}</Field.Label>
          <Switch.Root checked={pointerInteractive} onCheckedChange={(e) => setPointerInteractive(e.checked)} colorScheme="blue">
            <Switch.HiddenInput />
            <Switch.Control />
          </Switch.Root>
        </Field.Root>
      )}

      {/* VRM Import Dialog */}
      <VRMImportDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </Box>
  );
}

export default Live2D;
