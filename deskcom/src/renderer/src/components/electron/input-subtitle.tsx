import { FaTools } from 'react-icons/fa';
import {
  LuBell, LuSend, LuMic, LuMicOff, LuHand, LuX, LuLock, LuLockOpen, LuSettings, LuMessageSquare,
  LuCamera, LuMonitor, LuGlobe, LuBrain,
} from 'react-icons/lu';
import {
  Box,
  Button,
  Flex,
  Input,
  Spinner,
  Stack,
  Text,
  VStack,
  IconButton,
} from '@chakra-ui/react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useInputSubtitle } from '@/hooks/electron/use-input-subtitle';
import { useChatHistory } from '@/context/chat-history-context';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { inputSubtitleStyles } from './electron-style';
import { useForceIgnoreMouse } from '@/hooks/utils/use-force-ignore-mouse';
import { FormattedText } from '@/components/ui/formatted-text';
import { useCamera } from '@/context/camera-context';
import { useScreenCaptureContext } from '@/context/screen-capture-context';
import { useBrowser } from '@/context/browser-context';
import SettingsFloatingWindow from '@/components/floating/settings-floating-window';
import ChatHistoryFloatingWindow from '@/components/floating/chat-history-floating-window';
import MemoryFloatingWindow from '@/components/floating/memory-floating-window';
import TodoFloatingWindow from '@/components/floating/todo-floating-window';
import { getPlatform } from '@/platforms';

export function InputSubtitle() {
  const {
    inputValue,
    handleInputChange,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleInterrupt,
    handleMicToggle,
    handleSend,
    lastAIMessage,
    hasAIMessages,
    aiState,
    micOn,
    handleSelect,
    inputRef,
    mention,
  } = useInputSubtitle();

  const { messages } = useChatHistory();
  const { forceIgnoreMouse } = useForceIgnoreMouse();

  const {
    isStreaming: cameraOn,
    startCamera,
    stopCamera,
  } = useCamera();

  const {
    isStreaming: screenOn,
    startCapture,
    stopCapture,
  } = useScreenCaptureContext();

  const { browserViewData } = useBrowser();

  const toggleCamera = useCallback(() => {
    if (cameraOn) {
      stopCamera();
    } else {
      startCamera();
    }
  }, [cameraOn, startCamera, stopCamera]);

  const toggleScreen = useCallback(() => {
    if (screenOn) {
      stopCapture();
    } else {
      startCapture();
    }
  }, [screenOn, startCapture, stopCapture]);

  const handleBrowser = useCallback(() => {
    if (browserViewData?.debuggerUrl) {
      window.open(browserViewData.debuggerUrl, '_blank');
    }
  }, [browserViewData]);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [todoOpen, setTodoOpen] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

  const runningToolCalls = useMemo(
    () => messages.filter((msg) => msg.type === 'tool_call_status' && msg.status === 'running'),
    [messages],
  );
  const hasRunningTools = runningToolCalls.length > 0;
  const isProcessing = aiState === 'thinking-speaking' || aiState === 'loading';

  const {
    elementRef,
    isDragging,
    handleMouseDown,
  } = useDraggable({
    componentId: 'input-subtitle',
  });

  const togglePassthrough = useCallback(() => {
    getPlatform().toggleForceIgnoreMouse();
  }, []);

  const handleClose = useCallback(() => {
    setIsVisible(false);
  }, []);

  const handleOpen = () => {
    setIsVisible(true);
  };

  useEffect(() => {
    getPlatform().updateComponentHover('input-subtitle', true);
    return () => getPlatform().updateComponentHover('input-subtitle', false);
  }, []);

  useEffect(() => {
    const cleanup = getPlatform().onToggleInputSubtitle(() => {
      if (isVisible) {
        handleClose();
      } else {
        handleOpen();
      }
    });
    return () => cleanup?.();
  }, [handleClose, isVisible]);

  useEffect(() => {
    (window as any).inputSubtitle = {
      open: handleOpen,
      close: handleClose,
    };

    return () => {
      delete (window as any).inputSubtitle;
    };
  }, [handleClose]);

  if (!isVisible) return null;

  return (
    <>
      <Box
        ref={elementRef}
        {...inputSubtitleStyles.container}
        {...inputSubtitleStyles.draggableContainer(isDragging)}
        onMouseDown={handleMouseDown}
      >
        <Box {...inputSubtitleStyles.box}>
          {/* Floating window toggle buttons */}
          <Flex
            px={3}
            pt={2}
            pb={1}
            gap={1}
            borderBottom="1px solid"
            borderColor="whiteAlpha.100"
          >
            <IconButton
              aria-label="Settings"
              size="2xs"
              variant="ghost"
              color={settingsOpen ? "blue.300" : "whiteAlpha.600"}
              _hover={{ bg: 'whiteAlpha.200', color: 'whiteAlpha.900' }}
              onClick={() => setSettingsOpen(!settingsOpen)}
            >
              <LuSettings size={14} />
            </IconButton>
            <IconButton
              aria-label="Chat History"
              size="2xs"
              variant="ghost"
              color={historyOpen ? "blue.300" : "whiteAlpha.600"}
              _hover={{ bg: 'whiteAlpha.200', color: 'whiteAlpha.900' }}
              onClick={() => setHistoryOpen(!historyOpen)}
            >
              <LuMessageSquare size={14} />
            </IconButton>
            <IconButton
              aria-label="Long-Term Memory"
              size="2xs"
              variant="ghost"
              color={memoryOpen ? "blue.300" : "whiteAlpha.600"}
              _hover={{ bg: 'whiteAlpha.200', color: 'whiteAlpha.900' }}
              onClick={() => setMemoryOpen(!memoryOpen)}
            >
              <LuBrain size={14} />
            </IconButton>
            <IconButton
              aria-label="Reminders"
              size="2xs"
              variant="ghost"
              color={todoOpen ? "blue.300" : "whiteAlpha.600"}
              _hover={{ bg: 'whiteAlpha.200', color: 'whiteAlpha.900' }}
              onClick={() => setTodoOpen(!todoOpen)}
            >
              <LuBell size={14} />
            </IconButton>
            <Box flex={1} />
            <IconButton
              aria-label="Close subtitle"
              onClick={handleClose}
              {...inputSubtitleStyles.closeButton}
            >
              <LuX size={12} />
            </IconButton>
          </Flex>

          {hasAIMessages && (
            <VStack
              minH={lastAIMessage ? '32px' : '0px'}
              {...inputSubtitleStyles.messageStack}
            >
              {lastAIMessage && (
                <Text {...inputSubtitleStyles.messageText}>
                  <FormattedText text={lastAIMessage} />
                </Text>
              )}
            </VStack>
          )}

          <Box {...inputSubtitleStyles.statusBox}>
            <Flex align="center" justify="space-between" color="whiteAlpha.700">
              <Flex align="center" gap="2">
                <LuBell size={16} />
                {isProcessing && <Spinner size="xs" color="blue.300" />}
                <Text {...inputSubtitleStyles.statusText}>
                  {aiState}
                </Text>
              </Flex>

              <Flex gap="2">
                <IconButton
                  aria-label="Toggle microphone"
                  onClick={handleMicToggle}
                  {...inputSubtitleStyles.iconButton}
                >
                  {micOn ? <LuMic size={16} /> : <LuMicOff size={16} />}
                </IconButton>
                <IconButton
                  aria-label="Interrupt"
                  onClick={handleInterrupt}
                  {...inputSubtitleStyles.iconButton}
                >
                  <LuHand size={16} />
                </IconButton>
                <IconButton
                  aria-label={forceIgnoreMouse ? "Enable interaction" : "Enable passthrough"}
                  onClick={togglePassthrough}
                  {...inputSubtitleStyles.iconButton}
                  color={forceIgnoreMouse ? "blue.300" : "whiteAlpha.800"}
                >
                  {forceIgnoreMouse ? <LuLock size={16} /> : <LuLockOpen size={16} />}
                </IconButton>
                <IconButton
                  aria-label={cameraOn ? "Stop camera" : "Start camera"}
                  onClick={toggleCamera}
                  {...inputSubtitleStyles.iconButton}
                  color={cameraOn ? "blue.300" : "whiteAlpha.600"}
                >
                  <LuCamera size={16} />
                </IconButton>
                <IconButton
                  aria-label={screenOn ? "Stop screen share" : "Start screen share"}
                  onClick={toggleScreen}
                  {...inputSubtitleStyles.iconButton}
                  color={screenOn ? "blue.300" : "whiteAlpha.600"}
                >
                  <LuMonitor size={16} />
                </IconButton>
                <IconButton
                  aria-label={browserViewData ? "Open browser session" : "No browser session"}
                  onClick={handleBrowser}
                  {...inputSubtitleStyles.iconButton}
                  color={browserViewData ? "blue.300" : "whiteAlpha.600"}
                  opacity={browserViewData ? 1 : 0.4}
                >
                  <LuGlobe size={16} />
                </IconButton>
              </Flex>
            </Flex>
            {hasRunningTools && (
              <>
                <Flex mt="1" align="center" gap="1" color="blue.300" fontSize="xs">
                  <FaTools size={10} />
                  <Text css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {runningToolCalls[0]?.tool_name || 'Running tool...'}
                  </Text>
                </Flex>
              </>
            )}
          </Box>

          <Box {...inputSubtitleStyles.inputBox}>
            <Stack direction="row" gap="2" p="2">
              <Box position="relative" flex="1">
                <Input
                  ref={inputRef}
                  value={inputValue}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyPress}
                  onSelect={handleSelect}
                  onCompositionStart={handleCompositionStart}
                  onCompositionEnd={handleCompositionEnd}
                  placeholder="Type your message... (use @ to mention files)"
                  {...inputSubtitleStyles.input}
                />
                {mention.isOpen && (
                  <Box
                    position="absolute"
                    bottom="100%"
                    left="0"
                    right="0"
                    mb={1}
                    bg="rgba(30, 30, 58, 0.9)"
                    border="1px solid"
                    borderColor="#3a3a6a"
                    rounded="md"
                    boxShadow="0 -4px 20px rgba(0,0,0,0.6)"
                    maxH="240px"
                    overflowY="auto"
                    zIndex={9999}
                    css={{
                      backdropFilter: 'blur(12px)',
                      '&::-webkit-scrollbar': { width: '4px' },
                      '&::-webkit-scrollbar-track': { bg: 'transparent' },
                      '&::-webkit-scrollbar-thumb': { bg: '#3a3a6a', borderRadius: '2px' },
                    }}
                  >
                    {mention.suggestions.map((entry, idx) => (
                      <Box
                        key={entry.path}
                        px={3}
                        py={1.5}
                        cursor="pointer"
                        bg={idx === mention.selectedIndex ? '#2a2a5a' : 'transparent'}
                        color={idx === mention.selectedIndex ? '#ffffff' : '#c0c0e0'}
                        _hover={{ bg: '#2a2a5a', color: '#ffffff' }}
                        onClick={() => mention.insertMention(entry)}
                        fontSize="sm"
                        fontFamily="mono"
                      >
                        {entry.isDir ? '📁' : '📄'} {entry.name}
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
              <Button
                onClick={handleSend}
                {...inputSubtitleStyles.sendButton}
              >
                <LuSend size={16} />
              </Button>
            </Stack>
          </Box>
        </Box>
      </Box>

      <ChatHistoryFloatingWindow
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
      />
      <SettingsFloatingWindow
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
      <MemoryFloatingWindow
        open={memoryOpen}
        onClose={() => setMemoryOpen(false)}
      />
      <TodoFloatingWindow
        open={todoOpen}
        onClose={() => setTodoOpen(false)}
      />
    </>
  );
}
