import React, { createContext, useContext, useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { wsService, MessageEvent } from '@/services/websocket-service';

interface SongInfo {
  title: string;
  stream_url: string;
  video_url?: string;
}

interface MVInfo {
  title: string;
  stream_url: string;
  video_url: string;
  start_time?: number;
}

interface MusicPlayerState {
  currentSong: SongInfo | null;
  isPlaying: boolean;
  isRecommended: boolean;
  showFeedback: boolean;
  currentTime: number;
  duration: number;
  isRepeat: boolean;
  currentMV: MVInfo | null;
  play: (song: SongInfo, recommended?: boolean) => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  next: () => void;
  prev: () => void;
  seekTo: (time: number) => void;
  feedbackLike: () => void;
  feedbackDislike: () => void;
  clearFeedback: () => void;
  setShowFeedback: (show: boolean) => void;
  toggleRepeat: () => void;
  playMV: (videoUrl: string, title?: string, startTime?: number) => void;
  closeMV: () => void;
}

const MusicPlayerContext = createContext<MusicPlayerState | null>(null);

export function MusicPlayerProvider({ children }: { children: React.ReactNode }) {
  const [currentSong, setCurrentSong] = useState<SongInfo | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isRecommended, setIsRecommended] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isRepeat, setIsRepeat] = useState(false);
  const [currentMV, setCurrentMV] = useState<MVInfo | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isRepeatRef = useRef(false);

  const sendMessage = useCallback((message: object) => {
    wsService.sendMessage(message);
  }, []);

  const stopPlayback = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const play = useCallback((song: SongInfo, recommended: boolean = false) => {
    stopPlayback();
    setCurrentSong(song);
    setIsRecommended(recommended);
    setShowFeedback(false);

    const audio = new Audio(song.stream_url);
    audioRef.current = audio;

    audio.addEventListener('loadedmetadata', () => {
      setDuration(audio.duration || 0);
    });

    audio.addEventListener('timeupdate', () => {
      setCurrentTime(audio.currentTime);
    });

    audio.addEventListener('ended', () => {
      if (isRepeatRef.current) {
        // Replay the same song
        audio.currentTime = 0;
        audio.play().then(() => {
          setIsPlaying(true);
        }).catch(console.error);
      } else {
        setIsPlaying(false);
        if (recommended) {
          setShowFeedback(true);
        }
      }
    });

    audio.addEventListener('error', () => {
      console.error('Music playback error');
      setIsPlaying(false);
    });

    audio.play().then(() => {
      setIsPlaying(true);
    }).catch((err) => {
      console.error('Failed to start playback:', err);
      setIsPlaying(false);
    });
  }, [stopPlayback]);

  // Keep ref in sync with state
  useEffect(() => {
    isRepeatRef.current = isRepeat;
  }, [isRepeat]);

  const toggleRepeat = useCallback(() => {
    setIsRepeat(prev => !prev);
  }, []);

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  }, []);

  const resume = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(console.error);
    }
  }, []);

  const stop = useCallback(() => {
    stopPlayback();
    setCurrentSong(null);
    setIsRecommended(false);
    setShowFeedback(false);
    sendMessage({ type: 'music-stop' });
  }, [stopPlayback, sendMessage]);

  const next = useCallback(() => {
    stopPlayback();
    setShowFeedback(false);
    sendMessage({ type: 'music-next' });
  }, [stopPlayback, sendMessage]);

  const prev = useCallback(() => {
    stopPlayback();
    setShowFeedback(false);
    sendMessage({ type: 'music-prev' });
  }, [stopPlayback, sendMessage]);

  const feedbackLike = useCallback(() => {
    setShowFeedback(false);
    stopPlayback();
    sendMessage({ type: 'music-feedback', feedback: 'like' });
  }, [stopPlayback, sendMessage]);

  const feedbackDislike = useCallback(() => {
    setShowFeedback(false);
    stopPlayback();
    sendMessage({ type: 'music-feedback', feedback: 'dislike' });
  }, [stopPlayback, sendMessage]);

  const seekTo = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const clearFeedback = useCallback(() => {
    setShowFeedback(false);
  }, []);

  const playMV = useCallback((videoUrl: string, title?: string, startTime?: number) => {
    sendMessage({
      type: 'play-mv',
      video_url: videoUrl,
      title: title || '',
      start_time: startTime ?? 0,
    });
  }, [sendMessage]);

  const closeMV = useCallback(() => {
    setCurrentMV(null);
  }, []);

  // Subscribe to WebSocket messages for music events
  useEffect(() => {
    const sub = wsService.onMessage((message: MessageEvent) => {
      switch (message.type) {
        case 'youtube-invite':
          play(
            {
              title: message.title || '',
              stream_url: message.stream_url || '',
              video_url: message.video_url || '',
            },
            false,
          );
          break;
        case 'playlist-invite':
          play(
            {
              title: message.title || '',
              stream_url: message.stream_url || '',
              video_url: message.video_url || '',
            },
            false,
          );
          break;
        case 'music-play-song':
          play(
            {
              title: message.title || '',
              stream_url: message.stream_url || '',
              video_url: message.video_url || '',
            },
            message.is_recommended || false,
          );
          break;
        case 'music-stopped':
          stopPlayback();
          setCurrentSong(null);
          setIsRecommended(false);
          setShowFeedback(false);
          break;
        case 'music-no-prev':
          console.warn('No previous song:', message.message);
          break;
        case 'music-error':
          console.error('Music error:', message.message);
          break;
        case 'mv-invite':
          setCurrentMV({
            title: message.title || '',
            stream_url: message.stream_url || '',
            video_url: message.video_url || '',
            start_time: message.start_time || 0,
          });
          break;
        case 'mv-error':
          console.error('MV error:', message.message);
          setCurrentMV(null);
          break;
        default:
          break;
      }
    });
    return () => sub.unsubscribe();
  }, [play, stopPlayback]);

  const contextValue = useMemo(() => ({
    currentSong,
    isPlaying,
    isRecommended,
    showFeedback,
    currentTime,
    duration,
    isRepeat,
    currentMV,
    play,
    pause,
    resume,
    stop,
    next,
    prev,
    seekTo,
    feedbackLike,
    feedbackDislike,
    clearFeedback,
    setShowFeedback,
    toggleRepeat,
    playMV,
    closeMV,
  }), [currentSong, isPlaying, isRecommended, showFeedback, currentTime, duration, isRepeat, currentMV, play, pause, resume, stop, next, prev, seekTo, feedbackLike, feedbackDislike, clearFeedback, toggleRepeat, playMV, closeMV]);

  return (
    <MusicPlayerContext.Provider value={contextValue}>
      {children}
    </MusicPlayerContext.Provider>
  );
}

export function useMusicPlayer() {
  const context = useContext(MusicPlayerContext);
  if (!context) {
    throw new Error('useMusicPlayer must be used within a MusicPlayerProvider');
  }
  return context;
}
