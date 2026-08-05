import {
  Box,
  Text,
  Tabs,
  IconButton,
  Spinner,
  Button,
  Collapsible,
} from '@chakra-ui/react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FiTrash2, FiPlus } from 'react-icons/fi';
import { LuX } from 'react-icons/lu';
import { formatDistanceToNow } from 'date-fns';
import { FaTools, FaCheck, FaTimes, FaChevronDown, FaChevronRight, FaTerminal } from 'react-icons/fa';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { useChatHistoryFloating } from '@/hooks/floating/use-chat-history-floating';
import { FormattedText } from '@/components/ui/formatted-text';
import { useMusicPlayer } from '@/context/music-player-context';

interface ChatHistoryFloatingWindowProps {
  open: boolean;
  onClose: () => void;
}

function ChatHistoryFloatingWindow({ open, onClose }: ChatHistoryFloatingWindowProps) {
  const { t } = useTranslation();
  const {
    messages,
    historyList,
    currentHistoryUid,
    activeTab,
    setActiveTab,
    fetchAndSetHistory,
    deleteHistory,
    createNewHistory,
  } = useChatHistoryFloating();

  const musicPlayer = useMusicPlayer();

  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'chat-history-floating',
  });

  const [expandedToolIds, setExpandedToolIds] = useState<Set<string>>(new Set());

  const toggleToolExpand = useMemo(() => (toolId: string) => {
    setExpandedToolIds((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) {
        next.delete(toolId);
      } else {
        next.add(toolId);
      }
      return next;
    });
  }, []);

  const validMessages = useMemo(
    () => messages.filter((msg) => msg.content || msg.type === 'tool_call_status'),
    [messages],
  );

  if (!open) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      top="80px"
      left="20px"
      w="420px"
      maxH="70vh"
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
          {t('history.chatHistoryList')}
        </Text>
        <Box display="flex" gap={1}>
          <IconButton
            aria-label="New chat"
            size="2xs"
            variant="ghost"
            color="#8888bb"
            _hover={{ bg: '#2a2a4a', color: '#ffffff' }}
            onClick={createNewHistory}
          >
            <FiPlus size={14} />
          </IconButton>
          <IconButton
            aria-label="Close"
            size="2xs"
            variant="ghost"
            color="#8888bb"
            _hover={{ bg: '#2a2a4a', color: '#ffffff' }}
            onClick={onClose}
          >
            <LuX size={14} />
          </IconButton>
        </Box>
      </Box>

      <Tabs.Root value={activeTab} onValueChange={(details) => setActiveTab(details.value as 'history' | 'chat')}>
        <Tabs.List px={4} pt={2} borderBottom="1px solid" borderColor="#2a2a4a">
          <Tabs.Trigger
            value="chat"
            fontSize="xs"
            color="#8888bb"
            _selected={{ color: '#e0e0ff', fontWeight: 'semibold' }}
          >
            {t('history.currentChat')}
          </Tabs.Trigger>
          <Tabs.Trigger
            value="history"
            fontSize="xs"
            color="#8888bb"
            _selected={{ color: '#e0e0ff', fontWeight: 'semibold' }}
          >
            {t('history.chatHistoryList')}
          </Tabs.Trigger>
        </Tabs.List>

        <Box px={4} py={3} overflowY="auto" maxH="calc(70vh - 120px)" css={{
          '&::-webkit-scrollbar': { width: '6px' },
          '&::-webkit-scrollbar-track': { background: 'transparent' },
          '&::-webkit-scrollbar-thumb': { background: '#2a2a4a', borderRadius: '3px' },
        }}>
          <Tabs.ContentGroup>
            <Tabs.Content value="chat">
              {validMessages.length === 0 ? (
                <Text color="#666688" fontSize="sm" textAlign="center" py={8}>
                  {t('history.noMessages')}
                </Text>
              ) : (
                <Box spaceY={2}>
                  {validMessages.map((msg, idx) => {
                    if (msg.type === 'tool_call_status') {
                      const isCommand = msg.tool_name === 'run_command' || msg.tool_name === 'run_sudo_command';
                      const hasOutput = isCommand && msg.output_lines && msg.output_lines.length > 0;
                      const isExpanded = expandedToolIds.has(msg.tool_id || msg.id);
                      return (
                        <Box key={idx}>
                          <Box
                            display="flex"
                            alignItems="center"
                            gap={2}
                            fontSize="xs"
                            color={
                              msg.status === 'running' ? '#6666dd'
                              : msg.status === 'completed' ? '#44bb66'
                              : '#dd5555'
                            }
                            cursor={hasOutput ? 'pointer' : 'default'}
                            onClick={() => { if (hasOutput) toggleToolExpand(msg.tool_id || msg.id); }}
                            _hover={hasOutput ? { opacity: 0.8 } : undefined}
                          >
                            {isCommand ? <FaTerminal size={10} /> : <FaTools size={10} />}
                            <Text>{msg.tool_name || 'Tool'}</Text>
                            {msg.status === 'running' && <Spinner size="xs" />}
                            {msg.status === 'completed' && <FaCheck size={10} />}
                            {msg.status === 'error' && <FaTimes size={10} />}
                            {hasOutput && (
                              <Box ml="auto" color="#666688">
                                {isExpanded ? <FaChevronDown size={8} /> : <FaChevronRight size={8} />}
                              </Box>
                            )}
                          </Box>
                          {hasOutput && (
                            <Collapsible.Root open={isExpanded}>
                              <Collapsible.Content>
                                <Box
                                  mt={1}
                                  ml={4}
                                  p={2}
                                  bg="#0d0d1a"
                                  rounded="sm"
                                  fontFamily="monospace"
                                  fontSize="11px"
                                  color="#aabbcc"
                                  maxH="200px"
                                  overflowY="auto"
                                  css={{
                                    '&::-webkit-scrollbar': { width: '4px' },
                                    '&::-webkit-scrollbar-track': { background: 'transparent' },
                                    '&::-webkit-scrollbar-thumb': { background: '#2a2a4a', borderRadius: '2px' },
                                  }}
                                  whiteSpace="pre-wrap"
                                  wordBreak="break-all"
                                  lineHeight="1.5"
                                  onMouseDown={(e) => e.stopPropagation()}
                                  userSelect="text"
                                >
                                  {msg.output_lines?.join('\n') || msg.content}
                                </Box>
                              </Collapsible.Content>
                            </Collapsible.Root>
                          )}
                        </Box>
                      );
                    }
                    if (msg.type === 'youtube-invite') {
                      return (
                        <Box
                          key={idx}
                          p={2.5}
                          bg="#16162a"
                          rounded="md"
                          border="1px solid"
                          borderColor="#2a2a4a"
                          onMouseDown={(e) => e.stopPropagation()}
                          userSelect="text"
                        >
                          <Text fontSize="xs" color="#8888bb" mb={1}>AI</Text>
                          <Text fontSize="sm" color="#c0c0ff" mb={2}>
                            🎵 {msg.content}
                          </Text>
                          <Box display="flex" gap={2}>
                            <Button
                              size="2xs"
                              bg="#2a6a4a"
                              color="#ffffff"
                              _hover={{ bg: '#3a9a5a' }}
                              onClick={() => {
                                musicPlayer.play(
                                  {
                                    title: msg.content,
                                    stream_url: msg.stream_url || '',
                                    video_url: msg.video_url || '',
                                  },
                                  false,
                                );
                              }}
                            >
                              {musicPlayer.currentSong?.stream_url === msg.stream_url && musicPlayer.isPlaying
                                ? '⏸ Pause'
                                : '▶ Play'}
                            </Button>
                            <Button
                              size="2xs"
                              bg="#5a2a2a"
                              color="#ffffff"
                              _hover={{ bg: '#8a3a3a' }}
                              onClick={() => {
                                if (musicPlayer.currentSong?.stream_url === msg.stream_url) {
                                  musicPlayer.stop();
                                }
                              }}
                            >
                              ✕ Batal
                            </Button>
                          </Box>
                        </Box>
                      );
                    }
                    return (
                      <Box
                        key={idx}
                        p={2.5}
                        bg={msg.role === 'ai' ? '#16162a' : '#1a1a3e'}
                        rounded="md"
                        fontSize="sm"
                        color="#e0e0ff"
                        border="1px solid"
                        borderColor="#2a2a4a"
                        onMouseDown={(e) => e.stopPropagation()}
                        userSelect="text"
                      >
                        <Text fontSize="xs" color="#8888bb" mb={1}>
                          {msg.role === 'ai' ? 'AI' : 'You'}
                        </Text>
                        <Text><FormattedText text={msg.content} /></Text>
                      </Box>
                    );
                  })}
                </Box>
              )}
            </Tabs.Content>

            <Tabs.Content value="history">
              {historyList.length === 0 ? (
                <Text color="#666688" fontSize="sm" textAlign="center" py={8}>
                  {t('history.noHistory')}
                </Text>
              ) : (
                <Box spaceY={1}>
                  {historyList.map((history: any) => {
                    const latestMsg = history.latest_message;
                    const isSelected = currentHistoryUid === history.uid;
                    return (
                      <Box
                        key={history.uid}
                        p={2.5}
                        bg={isSelected ? '#1a1a3e' : '#0f0f23'}
                        rounded="md"
                        cursor="pointer"
                        _hover={{ bg: isSelected ? '#2a2a4e' : '#1a1a2e' }}
                        onClick={() => fetchAndSetHistory(history.uid)}
                        borderLeft={isSelected ? '3px solid' : '3px solid transparent'}
                        borderLeftColor={isSelected ? '#6666dd' : 'transparent'}
                        border="1px solid"
                        borderColor={isSelected ? '#2a2a4a' : 'transparent'}
                      >
                        <Box display="flex" justifyContent="space-between" alignItems="center">
                          <Text fontSize="xs" color="#8888bb">
                            {latestMsg?.timestamp
                              ? formatDistanceToNow(new Date(latestMsg.timestamp), { addSuffix: true })
                              : t('history.noMessages')}
                          </Text>
                          <IconButton
                            aria-label="Delete"
                            size="2xs"
                            variant="ghost"
                            color="#8888bb"
                            _hover={{ bg: '#2a2a4a', color: '#dd5555' }}
                            onClick={(e) => { e.stopPropagation(); deleteHistory(history.uid); }}
                            disabled={isSelected}
                          >
                            <FiTrash2 size={12} />
                          </IconButton>
                        </Box>
                          {latestMsg?.content && (
                          <Text
                            fontSize="xs"
                            color="#a0a0cc"
                            mt={1}
                            css={{
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                            }}
                          >
                            {latestMsg.content}
                          </Text>
                        )}
                      </Box>
                    );
                  })}
                </Box>
              )}
            </Tabs.Content>
          </Tabs.ContentGroup>
        </Box>
      </Tabs.Root>
    </Box>
  );
}

export default ChatHistoryFloatingWindow;
