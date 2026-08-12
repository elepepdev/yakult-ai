import { FaTools } from 'react-icons/fa';
import {
  LuBell, LuSend, LuMic, LuMicOff, LuHand, LuSettings, LuMessageSquare,
  LuCamera, LuMonitor, LuGlobe, LuBrain, LuListMusic,
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
import { useState, useCallback, useMemo } from 'react';
import { useInputSubtitle } from '@/hooks/electron/use-input-subtitle';
import { useChatHistory } from '@/context/chat-history-context';
import { FormattedText } from '@/components/ui/formatted-text';
import { useCamera } from '@/context/camera-context';
import { useScreenCaptureContext } from '@/context/screen-capture-context';
import { useBrowser } from '@/context/browser-context';
import { useSubtitle } from '@/context/subtitle-context';
import { FileAttachButton, FileAttachChips } from '@/components/ui/file-attach';
import SettingsFloatingWindow from '@/components/floating/settings-floating-window';
import ChatHistoryFloatingWindow from '@/components/floating/chat-history-floating-window';
import MemoryFloatingWindow from '@/components/floating/memory-floating-window';
import TodoFloatingWindow from '@/components/floating/todo-floating-window';
import PlaylistFloatingWindow from '@/components/floating/playlist-floating-window';

export function WebInputSubtitle() {
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
    attach,
  } = useInputSubtitle();

  const { messages } = useChatHistory();

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
  const { dismissSubconscious } = useSubtitle();

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
  const [playlistOpen, setPlaylistOpen] = useState(false);

  const runningToolCalls = useMemo(
    () => messages.filter((msg) => msg.type === 'tool_call_status' && msg.status === 'running'),
    [messages],
  );
  const hasRunningTools = runningToolCalls.length > 0;
  const isProcessing = aiState === 'thinking-speaking' || aiState === 'loading';

  const iconButtonStyle = {
    size: 'xs' as const,
    variant: 'ghost' as const,
    color: '#c0c0e0',
    _hover: { bg: 'whiteAlpha.200', color: '#ffffff' },
  };

  return (
    <>
      <Box
        position="fixed"
        bottom="24px"
        left="50%"
        transform="translateX(-50%)"
        zIndex={1000}
        w="420px"
        maxW="calc(100vw - 32px)"
        borderRadius="var(--sk-radius-card)"
        overflow="hidden"
        border="1.5px solid"
        borderColor="var(--sk-outline)"
        bg="var(--sk-paper-glass)"
        css={{
          backdropFilter: 'blur(18px)',
          WebkitBackdropFilter: 'blur(18px)',
        }}
        boxShadow="0 8px 40px rgba(0,0,0,0.45)"
      >
        {/* Floating window toggle buttons */}
        <Flex
          px={3}
          py={1.5}
          gap={1}
          borderBottom="1.5px solid"
          borderColor="var(--sk-outline)"
          bg="var(--sk-paper-deep)"
        >
          <IconButton
            aria-label="Settings"
            {...iconButtonStyle}
            color={settingsOpen ? "blue.300" : "whiteAlpha.600"}
            onClick={() => setSettingsOpen(!settingsOpen)}
          >
            <LuSettings size={14} />
          </IconButton>
          <IconButton
            aria-label="Chat History"
            {...iconButtonStyle}
            color={historyOpen ? "blue.300" : "whiteAlpha.600"}
            onClick={() => setHistoryOpen(!historyOpen)}
          >
            <LuMessageSquare size={14} />
          </IconButton>
          <IconButton
            aria-label="Long-Term Memory"
            {...iconButtonStyle}
            color={memoryOpen ? "blue.300" : "whiteAlpha.600"}
            onClick={() => setMemoryOpen(!memoryOpen)}
          >
            <LuBrain size={14} />
          </IconButton>
          <IconButton
            aria-label="Reminders"
            {...iconButtonStyle}
            color={todoOpen ? "blue.300" : "whiteAlpha.600"}
            onClick={() => setTodoOpen(!todoOpen)}
          >
            <LuBell size={14} />
          </IconButton>
          <IconButton
            aria-label="Playlists"
            {...iconButtonStyle}
            color={playlistOpen ? "blue.300" : "whiteAlpha.600"}
            onClick={() => setPlaylistOpen(!playlistOpen)}
          >
            <LuListMusic size={14} />
          </IconButton>
        </Flex>

        {hasAIMessages && (
          <VStack
            minH={lastAIMessage ? '32px' : '0px'}
            p="3"
            gap={1}
            alignItems="stretch"
            justify="flex-end"
            bg="var(--sk-paper-deep)"
          >
            {lastAIMessage && (
              <Text
                color="#e6e6ff"
                fontSize="sm"
                lineHeight="1.5"
              >
                <FormattedText text={lastAIMessage} />
              </Text>
            )}
          </VStack>
        )}

        <Box
          px="3"
          py="2"
          borderTop="1.5px solid"
          borderColor="var(--sk-outline)"
          bg="var(--sk-paper-deep)"
        >
          <Flex align="center" justify="space-between" color="whiteAlpha.700">
            <Flex align="center" gap="2">
              <LuBell size={16} />
              {isProcessing && <Spinner size="xs" color="blue.300" />}
              <Text fontSize="xs" color="#c0c0e0">{aiState}</Text>
            </Flex>

            <Flex gap="1">
              <IconButton
                aria-label="Toggle microphone"
                onClick={handleMicToggle}
                {...iconButtonStyle}
                color={micOn ? "blue.300" : "whiteAlpha.600"}
              >
                {micOn ? <LuMic size={16} /> : <LuMicOff size={16} />}
              </IconButton>
              <IconButton
                aria-label="Interrupt"
                onClick={handleInterrupt}
                {...iconButtonStyle}
              >
                <LuHand size={16} />
              </IconButton>
              <IconButton
                aria-label={cameraOn ? "Stop camera" : "Start camera"}
                onClick={toggleCamera}
                {...iconButtonStyle}
                color={cameraOn ? "blue.300" : "whiteAlpha.600"}
              >
                <LuCamera size={16} />
              </IconButton>
              <IconButton
                aria-label={screenOn ? "Stop screen share" : "Start screen share"}
                onClick={toggleScreen}
                {...iconButtonStyle}
                color={screenOn ? "blue.300" : "whiteAlpha.600"}
              >
                <LuMonitor size={16} />
              </IconButton>
              <IconButton
                aria-label={browserViewData ? "Open browser session" : "No browser session"}
                onClick={handleBrowser}
                {...iconButtonStyle}
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

        <Box
          borderTop="1px solid"
          borderColor="whiteAlpha.100"
          bg="rgba(255,255,255,0.02)"
        >
          <FileAttachChips files={attach.files} onRemove={attach.removeFile} />
          <Stack direction="row" gap="2" p="2.5">
            <input
              ref={attach.fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                attach.onFilesSelected(e.target.files);
                e.target.value = '';
              }}
            />
            <Box position="relative" flex="1">
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={handleKeyPress}
                onSelect={handleSelect}
                onFocus={dismissSubconscious}
                onCompositionStart={handleCompositionStart}
                onCompositionEnd={handleCompositionEnd}
                placeholder="Type your message... (use @ to mention files)"
                size="sm"
                bg="rgba(0,0,0,0.25)"
                color="#e0e0ff"
                _placeholder={{ color: '#7777aa' }}
                border="1px solid"
                borderColor="whiteAlpha.200"
                _focus={{
                  borderColor: 'rgba(120,120,220,0.6)',
                  outline: 'none',
                  boxShadow: '0 0 0 1px rgba(120,120,220,0.4)',
                }}
                _hover={{ borderColor: 'whiteAlpha.300' }}
                flex="1"
                rounded="lg"
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
            <FileAttachButton onPick={attach.openPicker} uploading={attach.uploading} />
            <Button
              onClick={handleSend}
              p="1.5"
              bg="rgba(120,120,220,0.35)"
              rounded="lg"
              _hover={{ bg: 'rgba(120,120,220,0.5)' }}
              transition="colors"
              color="#e0e0ff"
              size="sm"
            >
              <LuSend size={16} />
            </Button>
          </Stack>
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
      <PlaylistFloatingWindow
        open={playlistOpen}
        onClose={() => setPlaylistOpen(false)}
      />
    </>
  );
}
