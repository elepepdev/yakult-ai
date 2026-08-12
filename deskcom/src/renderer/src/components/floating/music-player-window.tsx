import {
  Box,
  Text,
  IconButton,
  Button,
  HStack,
} from '@chakra-ui/react';
import { useCallback } from 'react';
import {
  LuPlay,
  LuPause,
  LuRepeat,
  LuSkipBack,
  LuSkipForward,
  LuSquare,
  LuMusic,
  LuMonitorPlay,
} from 'react-icons/lu';
import { Slider } from '@/components/ui/slider';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { WashiTape } from '@/components/ui/washi-tape';
import { useMusicPlayer } from '@/context/music-player-context';

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function MusicPlayerWindow() {
  const {
    currentSong,
    isPlaying,
    showFeedback,
    currentTime,
    duration,
    pause,
    resume,
    stop,
    next,
    prev,
    seekTo,
    feedbackLike,
    feedbackDislike,
    isRepeat,
    toggleRepeat,
    playMV,
  } = useMusicPlayer();

  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'music-player',
  });

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === ' ' && currentSong) {
      e.preventDefault();
      e.stopPropagation();
      if (isPlaying) pause(); else resume();
    }
  }, [currentSong, isPlaying, pause, resume]);

  if (!currentSong) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      bottom="90px"
      right="20px"
      w="280px"
      bg="#1a1a2e"
      border="1px solid"
      borderColor="#2a2a4a"
      rounded="xl"
      boxShadow="0 8px 32px rgba(0,0,0,0.6)"
      zIndex={3000}
      overflow="hidden"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onMouseDown={handleMouseDown}
      cursor={isDragging ? 'grabbing' : 'default'}
      userSelect="none"
      css={{ outline: 'none' }}
    >
      {/* Header */}
      <Box
        display="flex"
        alignItems="center"
        gap={2}
        px={3}
        py={2}
        bg="#16162a"
        borderBottom="1px solid"
        borderColor="#2a2a4a"
      >
        <LuMusic size={14} color="#6666dd" />
        <Text fontSize="xs" fontWeight="bold" color="#8888bb" flex={1}>
          Music Player
        </Text>
      </Box>

      {/* Song info */}
      <Box px={3} py={2}>
        <Text fontSize="xs" color="#8888bb" mb={0.5}>
          Now Playing
        </Text>
        <Text
          fontSize="sm"
          color="#e0e0ff"
          fontWeight="semibold"
          title={currentSong.title}
          css={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {currentSong.title}
        </Text>
      </Box>

      {/* Seek bar */}
      <Box px={3} pb={1}>
        <Slider
          value={[currentTime]}
          max={duration || 100}
          step={0.5}
          size="sm"
          colorPalette="purple"
          onValueChange={(e) => seekTo(e.value[0])}
          onValueChangeEnd={(e) => seekTo(e.value[0])}
        />
        <HStack justify="space-between" mt={0.5}>
          <Text fontSize="2xs" color="#6666aa">
            {formatTime(currentTime)}
          </Text>
          <Text fontSize="2xs" color="#6666aa">
            {formatTime(duration)}
          </Text>
        </HStack>
      </Box>

      {/* Controls */}
      <Box
        display="flex"
        alignItems="center"
        justifyContent="center"
        gap={2}
        px={3}
        pb={3}
      >
        <IconButton
          aria-label="Previous"
          size="sm"
          variant="ghost"
          color="#8888bb"
          _hover={{ bg: '#2a2a4a', color: '#e0e0ff' }}
          onClick={prev}
        >
          <LuSkipBack size={16} />
        </IconButton>

        <IconButton
          aria-label={isPlaying ? 'Pause' : 'Play'}
          size="md"
          rounded="full"
          bg="#3a3a6a"
          color="#e0e0ff"
          _hover={{ bg: '#4a4a8a' }}
          onClick={isPlaying ? pause : resume}
        >
          {isPlaying ? <LuPause size={18} /> : <LuPlay size={18} />}
        </IconButton>

        <IconButton
          aria-label="Stop"
          size="sm"
          variant="ghost"
          color="#8888bb"
          _hover={{ bg: '#2a2a4a', color: '#dd5555' }}
          onClick={stop}
        >
          <LuSquare size={16} />
        </IconButton>

        <IconButton
          aria-label={isRepeat ? 'Repeat On' : 'Repeat Off'}
          size="sm"
          variant="ghost"
          color={isRepeat ? '#7c3aed' : '#8888bb'}
          bg={isRepeat ? 'rgba(124, 58, 237, 0.15)' : 'transparent'}
          _hover={{
            bg: isRepeat ? 'rgba(124, 58, 237, 0.25)' : '#2a2a4a',
            color: isRepeat ? '#a78bfa' : '#e0e0ff',
          }}
          onClick={toggleRepeat}
          transition="all 0.2s"
          title={isRepeat ? 'Repeat: On' : 'Repeat: Off'}
        >
          <LuRepeat size={16} />
        </IconButton>

        <IconButton
          aria-label="Next"
          size="sm"
          variant="ghost"
          color="#8888bb"
          _hover={{ bg: '#2a2a4a', color: '#e0e0ff' }}
          onClick={next}
        >
          <LuSkipForward size={16} />
        </IconButton>
      </Box>

      {/* Feedback popup */}
      {showFeedback && (
        <Box
          p={3}
          bg="#1a1a3e"
          borderTop="1px solid"
          borderColor="#2a2a4a"
        >
          <Text fontSize="xs" color="#c0c0ff" mb={2} textAlign="center">
            Do you like this type of music?
          </Text>
          <Box display="flex" gap={2} justifyContent="center">
            <Button
              size="2xs"
              bg="#2a6a4a"
              color="#ffffff"
              _hover={{ bg: '#3a9a5a' }}
              onClick={feedbackLike}
            >
              Yes
            </Button>
            <Button
              size="2xs"
              bg="#5a2a2a"
              color="#ffffff"
              _hover={{ bg: '#8a3a3a' }}
              onClick={feedbackDislike}
            >
              No
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}

export default MusicPlayerWindow;
