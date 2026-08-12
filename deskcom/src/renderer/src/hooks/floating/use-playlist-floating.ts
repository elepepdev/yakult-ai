import { useState, useCallback, useEffect } from 'react';
import { wsService } from '@/services/websocket-service';

export interface PlaylistSong {
  id: string;
  title: string;
  video_url: string;
  duration: number;
  thumbnail: string;
  file_path: string;
  added_at: string;
}

export interface Playlist {
  id: string;
  name: string;
  created_at: string;
  songs: PlaylistSong[];
}

export interface SearchResult {
  title: string;
  video_url: string;
  duration: number;
  thumbnail: string;
}

export function usePlaylistFloating() {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const subscription = wsService.onMessage((message) => {
      if (message?.type === 'playlists') {
        setPlaylists(message.data || []);
        setLoading(false);
      }
      if (message?.type === 'download-song-result') {
        wsService.sendMessage({ type: 'fetch-playlists' });
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const fetchPlaylists = useCallback(() => {
    setLoading(true);
    wsService.sendMessage({ type: 'fetch-playlists' });
  }, []);

  const createPlaylist = useCallback((name: string) => {
    wsService.sendMessage({ type: 'create-playlist', name });
    wsService.sendMessage({ type: 'fetch-playlists' });
  }, []);

  const deletePlaylist = useCallback((id: string) => {
    wsService.sendMessage({ type: 'delete-playlist', id });
    setPlaylists((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const renamePlaylist = useCallback((id: string, name: string) => {
    wsService.sendMessage({ type: 'rename-playlist', id, name });
    setPlaylists((prev) =>
      prev.map((p) => (p.id === id ? { ...p, name } : p)),
    );
  }, []);

  const addSong = useCallback((playlistId: string, song: Partial<PlaylistSong>) => {
    wsService.sendMessage({ type: 'add-song', playlist_id: playlistId, song });
    wsService.sendMessage({ type: 'fetch-playlists' });
  }, []);

  const removeSong = useCallback((playlistId: string, songId: string) => {
    wsService.sendMessage({ type: 'remove-song', playlist_id: playlistId, song_id: songId });
    setPlaylists((prev) =>
      prev.map((p) =>
        p.id === playlistId
          ? { ...p, songs: p.songs.filter((s) => s.id !== songId) }
          : p,
      ),
    );
  }, []);

  const downloadSong = useCallback((playlistId: string, videoUrl: string, title: string, video: boolean = false) => {
    wsService.sendMessage({
      type: 'download-song',
      playlist_id: playlistId,
      video_url: videoUrl,
      title,
      video,
    });
  }, []);

  const reorderSong = useCallback((playlistId: string, songId: string, newIndex: number) => {
    wsService.sendMessage({
      type: 'reorder-song',
      playlist_id: playlistId,
      song_id: songId,
      new_index: newIndex,
    });
    wsService.sendMessage({ type: 'fetch-playlists' });
  }, []);

  const playPlaylist = useCallback((playlistId: string, shuffle: boolean = false, startIndex: number = 0) => {
    wsService.sendMessage({ type: 'playlist-play', playlist_id: playlistId, shuffle, start_index: startIndex });
  }, []);

  const searchYoutube = useCallback((query: string) => {
    wsService.sendMessage({ type: 'search-youtube', query });
  }, []);

  return {
    playlists,
    setPlaylists,
    loading,
    fetchPlaylists,
    createPlaylist,
    deletePlaylist,
    renamePlaylist,
    addSong,
    removeSong,
    downloadSong,
    reorderSong,
    playPlaylist,
    searchYoutube,
  };
}
