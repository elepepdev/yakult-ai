import {
  Tabs,
  Box,
  Text,
  IconButton,
} from '@chakra-ui/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LuX } from 'react-icons/lu';
import { useDraggable } from '@/hooks/electron/use-draggable';
import General from './setting/general';
import Live2D from './setting/live2d';
import ASR from './setting/asr';
import TTS from './setting/tts';
import Agent from './setting/agent';
import About from './setting/about';

interface SettingsFloatingWindowProps {
  open: boolean;
  onClose: () => void;
}

const tabItems = [
  { value: 'general', labelKey: 'settings.tabs.general' },
  { value: 'live2d', labelKey: 'settings.tabs.live2d' },
  { value: 'asr', labelKey: 'settings.tabs.asr' },
  { value: 'tts', labelKey: 'settings.tabs.tts' },
  { value: 'agent', labelKey: 'settings.tabs.agent' },
  { value: 'about', labelKey: 'settings.tabs.about' },
];

function SettingsFloatingWindow({ open, onClose }: SettingsFloatingWindowProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('general');
  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'settings-floating',
  });

  if (!open) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      top="80px"
      right="20px"
      w="520px"
      maxH="80vh"
      bg="#1a1a2e"
      border="1px solid"
      borderColor="#2a2a4a"
      rounded="xl"
      boxShadow="0 8px 32px rgba(0,0,0,0.6)"
      zIndex={2000}
      overflow="hidden"
      onMouseDown={handleMouseDown}
      cursor={isDragging ? 'grabbing' : 'default'}
      userSelect="none"
    >
      <Box
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        px={5}
        py={3.5}
        borderBottom="1px solid"
        borderColor="#2a2a4a"
        bg="#16162a"
      >
        <Text fontSize="md" fontWeight="bold" color="#e0e0ff">
          {t('common.settings')}
        </Text>
        <IconButton
          aria-label="Close settings"
          size="2xs"
          variant="ghost"
          color="#8888bb"
          _hover={{ bg: '#2a2a4a', color: '#ffffff' }}
          onClick={onClose}
        >
          <LuX size={16} />
        </IconButton>
      </Box>

      <Box px={5} py={4} overflowY="auto" maxH="calc(80vh - 100px)" css={{
        '&::-webkit-scrollbar': { width: '6px' },
        '&::-webkit-scrollbar-track': { background: 'transparent' },
        '&::-webkit-scrollbar-thumb': { background: '#2a2a4a', borderRadius: '3px' },
      }}>
        <Tabs.Root
          defaultValue="general"
          value={activeTab}
          onValueChange={(details) => setActiveTab(details.value)}
          orientation="vertical"
          size="sm"
        >
          <Box display="flex" gap={5}>
            <Tabs.List minW="110px">
              {tabItems.map((tab) => (
                <Tabs.Trigger
                  key={tab.value}
                  value={tab.value}
                  fontSize="xs"
                  justifyContent="flex-start"
                  px={3}
                  py={2.5}
                  mb={1}
                  rounded="md"
                  color="#8888bb"
                  _selected={{
                    bg: '#2a2a4a',
                    color: '#e0e0ff',
                    fontWeight: 'semibold',
                  }}
                  _hover={{ color: '#c0c0ff' }}
                >
                  {t(tab.labelKey)}
                </Tabs.Trigger>
              ))}
            </Tabs.List>

            <Box flex={1} minW={0}>
              <Tabs.ContentGroup>
                <Tabs.Content value="general"><General /></Tabs.Content>
                <Tabs.Content value="live2d"><Live2D /></Tabs.Content>
                <Tabs.Content value="asr"><ASR /></Tabs.Content>
                <Tabs.Content value="tts"><TTS /></Tabs.Content>
                <Tabs.Content value="agent"><Agent /></Tabs.Content>
                <Tabs.Content value="about"><About /></Tabs.Content>
              </Tabs.ContentGroup>
            </Box>
          </Box>
        </Tabs.Root>
      </Box>
    </Box>
  );
}

export default SettingsFloatingWindow;
