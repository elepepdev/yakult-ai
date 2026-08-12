import { Box, Text, IconButton, HStack, Spinner } from '@chakra-ui/react';
import { useEffect, useRef, useState } from 'react';
import { LuX, LuVideo } from 'react-icons/lu';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { useMusicPlayer } from '@/context/music-player-context';
import { WashiTape } from '@/components/ui/washi-tape';

function MVWindow() {
  const { currentMV, closeMV } = useMusicPlayer();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [playError, setPlayError] = useState(false);
  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'mv-window',
  });

  useEffect(() => {
    setLoading(true);
    setPlayError(false);
    const el = videoRef.current;
    if (el && currentMV?.stream_url) {
      el.src = currentMV.stream_url;
      el.play().catch(() => setPlayError(true));
    }
  }, [currentMV]);

  if (!currentMV) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      bottom="90px"
      right="320px"
      w="400px"
      bg="var(--sk-paper)"
      borderWidth="var(--sk-border)"
      borderColor="var(--sk-outline)"
      borderRadius="var(--sk-radius-card)"
      className="sk-settle"
      boxShadow="0 8px 32px rgba(0,0,0,0.6)"
      zIndex={3001}
      overflow="hidden"
      onMouseDown={handleMouseDown}
      cursor={isDragging ? 'grabbing' : 'default'}
      userSelect="none"
    >
      {/* Header */}
      <Box
        position="relative"
        display="flex"
        alignItems="center"
        gap={2}
        px={3}
        py={2}
        bg="var(--sk-paper-deep)"
        borderBottomWidth="var(--sk-border)"
        borderColor="var(--sk-outline)"
      >
        <WashiTape color="var(--sk-danger)" />
        <LuVideo size={14} color="var(--sk-pencil-deep)" />
        <Text fontSize="xs" fontWeight="bold" color="var(--sk-ink-faint)" flex={1} css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {currentMV.title}
        </Text>
        <IconButton
          aria-label="Close"
          size="2xs"
          variant="ghost"
          color="var(--sk-ink-faint)"
          _hover={{ bg: 'var(--sk-outline)', color: 'var(--sk-danger)' }}
          onClick={closeMV}
        >
          <LuX size={14} />
        </IconButton>
      </Box>

      {/* Video */}
      <Box position="relative" bg="#000" w="100%" css={{ aspectRatio: '16 / 9' }}>
        <video
          ref={videoRef}
          controls
          autoPlay
          style={{ width: '100%', height: '100%', display: 'block' }}
          onLoadedData={() => setLoading(false)}
          onError={() => {
            setLoading(false);
            setPlayError(true);
          }}
        />
        {loading && (
          <Box
            position="absolute"
            top="0"
            left="0"
            right="0"
            bottom="0"
            display="flex"
            alignItems="center"
            justifyContent="center"
            pointerEvents="none"
          >
            <Spinner color="var(--sk-pencil)" size="md" />
          </Box>
        )}
        {playError && !loading && (
          <Box
            position="absolute"
            top="0"
            left="0"
            right="0"
            bottom="0"
            display="flex"
            alignItems="center"
            justifyContent="center"
            pointerEvents="none"
          >
            <Text fontSize="xs" color="#ffffff">
              Gagal memuat video
            </Text>
          </Box>
        )}
      </Box>

      {/* Footer */}
      <HStack px={3} py={2} justify="space-between" bg="var(--sk-paper-deep)" borderTopWidth="var(--sk-border)" borderColor="var(--sk-outline)">
        <Text fontSize="10px" color="var(--sk-ink-mute)">
          Music Video
        </Text>
        <Text fontSize="10px" color="var(--sk-ink-mute)" css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxW: '260px' }}>
          {currentMV.video_url}
        </Text>
      </HStack>
    </Box>
  );
}

export default MVWindow;
