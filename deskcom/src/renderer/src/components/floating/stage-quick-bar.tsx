import { Box, HStack, IconButton } from '@chakra-ui/react';
import { FaCompress, FaDesktop, FaThLarge, FaMagnet } from 'react-icons/fa';
import { useStageLayout } from '@/context/stage-layout-context';
import { Tooltip } from '@/components/ui/tooltip';

export function StageQuickBar() {
  const { preset, setPreset, snapToGrid, setSnapToGrid } = useStageLayout();

  return (
    <Box
      position="fixed"
      top="12px"
      right="16px"
      zIndex={2100}
      bg="var(--sk-paper)"
      borderWidth="var(--sk-border)"
      borderColor="var(--sk-outline)"
      borderRadius="var(--sk-radius-card)"
      px={2.5}
      py={1.5}
      boxShadow="0 4px 16px rgba(0,0,0,0.3)"
      className="sk-settle"
    >
      <HStack gap={1.5}>
        <Tooltip content="Compact Mode (Hanya Karakter & Bubble)">
          <IconButton
            aria-label="Compact Mode"
            size="xs"
            variant={preset === 'compact' ? 'solid' : 'ghost'}
            colorPalette={preset === 'compact' ? 'blue' : 'gray'}
            onClick={() => setPreset('compact')}
          >
            <FaCompress size={12} />
          </IconButton>
        </Tooltip>

        <Tooltip content="Focus Mode (Chat & Music di Samping)">
          <IconButton
            aria-label="Focus Mode"
            size="xs"
            variant={preset === 'focus' ? 'solid' : 'ghost'}
            colorPalette={preset === 'focus' ? 'blue' : 'gray'}
            onClick={() => setPreset('focus')}
          >
            <FaDesktop size={12} />
          </IconButton>
        </Tooltip>

        <Tooltip content="Studio Mode (Semua Panel Terbuka)">
          <IconButton
            aria-label="Studio Mode"
            size="xs"
            variant={preset === 'studio' ? 'solid' : 'ghost'}
            colorPalette={preset === 'studio' ? 'blue' : 'gray'}
            onClick={() => setPreset('studio')}
          >
            <FaThLarge size={12} />
          </IconButton>
        </Tooltip>

        <Box w="1px" h="16px" bg="var(--sk-outline)" mx={1} />

        <Tooltip content={snapToGrid ? 'Magnet Layout Active' : 'Magnet Layout Inactive'}>
          <IconButton
            aria-label="Toggle Magnet Snap"
            size="xs"
            variant={snapToGrid ? 'solid' : 'ghost'}
            colorPalette={snapToGrid ? 'teal' : 'gray'}
            onClick={() => setSnapToGrid(!snapToGrid)}
          >
            <FaMagnet size={12} />
          </IconButton>
        </Tooltip>
      </HStack>
    </Box>
  );
}
