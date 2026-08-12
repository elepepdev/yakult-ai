import {
  Box,
  Text,
  IconButton,
  Button,
  Input,
  Spinner,
  HStack,
  VStack,
  useToast,
} from '@chakra-ui/react';
import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { LuX, LuListMusic, LuSearch, LuPlus, LuPlay, LuShuffle, LuDownload, LuArrowLeft } from 'react-icons/lu';
import { FiTrash2, FiEdit2, FiCheck } from 'react-icons/fi';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { usePlaylistFloating, Playlist, PlaylistSong, SearchResult } from '@/hooks/floating/use-playlist-floating';
import { WashiTape } from '@/components/ui/washi-tape';
import { wsService } from '@/services/websocket-service';

function formatDuration(d: number): string {
  if (!d || d <= 0) return '';
  const m = Math.floor(d / 60);
  const s = Math.floor(d % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function CreatePlaylistRow({ onCreate }: { onCreate: (name: string) => void }) {
  const [name, setName] = useState('');
  const [show, setShow] = useState(false);

  const submit = () => {
    const n = name.trim();
    if (n) {
      onCreate(n);
      setName('');
      setShow(false);
    }
  };

  if (!show) {
    return (
      <Button size="2xs" variant="ghost" color="var(--sk-pencil-deep)" onClick={() => setShow(true)}>
        <LuPlus size={12} /> New Playlist
      </Button>
    );
  }
  return (
    <HStack gap={1}>
      <Input
        size="xs"
        value={name}
        autoFocus
        placeholder="Nama playlist..."
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
        bg="var(--sk-paper-input)"
        borderColor="var(--sk-outline-soft)"
        color="var(--sk-ink)"
      />
      <IconButton aria-label="Create" size="2xs" color="var(--sk-success)" onClick={submit}>
        <FiCheck size={12} />
      </IconButton>
    </HStack>
  );
}

function RenameRow({ initial, onSave, onCancel }: { initial: string; onSave: (n: string) => void; onCancel: () => void }) {
  const [name, setName] = useState(initial);
  return (
    <HStack gap={1} flex={1}>
      <Input
        size="xs"
        value={name}
        autoFocus
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onSave(name.trim()); }}
        bg="var(--sk-paper-input)"
        borderColor="var(--sk-outline-soft)"
        color="var(--sk-ink)"
      />
      <IconButton aria-label="Save" size="2xs" color="var(--sk-success)" onClick={() => onSave(name.trim())}>
        <FiCheck size={12} />
      </IconButton>
      <IconButton aria-label="Cancel" size="2xs" color="var(--sk-ink-dim)" onClick={onCancel}>
        <LuX size={12} />
      </IconButton>
    </HStack>
  );
}

function SongRow({
  song,
  onPlay,
  onRemove,
  onDownload,
}: {
  song: PlaylistSong;
  onPlay: () => void;
  onRemove: () => void;
  onDownload: () => void;
}) {
  return (
    <HStack
      gap={2}
      w="100%"
      p={2}
      bg="var(--sk-paper-deep)"
      rounded="md"
      borderWidth="var(--sk-border)"
      borderColor="var(--sk-outline)"
    >
      <IconButton aria-label="Play" size="2xs" variant="ghost" color="var(--sk-success)" onClick={onPlay}>
        <LuPlay size={12} />
      </IconButton>
      <Box flex={1} minW={0}>
        <Text fontSize="sm" color="var(--sk-ink)" lineHeight="1.3" css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {song.title}
        </Text>
        {formatDuration(song.duration) && (
          <Text fontSize="10px" color="var(--sk-ink-dim)">{formatDuration(song.duration)}</Text>
        )}
      </Box>
      <IconButton aria-label="Download" size="2xs" variant="ghost" color="var(--sk-pencil-deep)" onClick={onDownload}>
        <LuDownload size={12} />
      </IconButton>
      <IconButton aria-label="Remove" size="2xs" variant="ghost" color="var(--sk-danger)" onClick={onRemove}>
        <FiTrash2 size={12} />
      </IconButton>
    </HStack>
  );
}

interface PlaylistFloatingWindowProps {
  open: boolean;
  onClose: () => void;
}

function PlaylistFloatingWindow({ open, onClose }: PlaylistFloatingWindowProps) {
  const {
    playlists, loading, fetchPlaylists, createPlaylist, deletePlaylist, renamePlaylist,
    addSong, removeSong, downloadSong, playPlaylist, searchYoutube,
  } = usePlaylistFloating();
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (open) {
      fetchPlaylists();
    }
  }, [open, fetchPlaylists]);

  useEffect(() => {
    const sub = wsService.onMessage((message) => {
      if (message?.type === 'youtube-search-results') {
        setSearchResults(message.results || []);
        setSearching(false);
      }
      if (message?.type === 'playlist-error') {
        toast.create({
          title: message.message || 'Playlist error',
          type: 'error',
          duration: 2000,
        });
      }
    });
    return () => sub.unsubscribe();
  }, [toast]);

  const selected = useMemo(
    () => playlists.find((p) => p.id === selectedId) || null,
    [playlists, selectedId],
  );

  const handleSearch = useCallback((q: string) => {
    setQuery(q);
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    if (!q.trim()) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    searchDebounce.current = setTimeout(() => searchYoutube(q.trim()), 500);
  }, [searchYoutube]);

  const handleCreate = useCallback((name: string) => {
    createPlaylist(name);
  }, [createPlaylist]);

  const handleRename = useCallback((id: string, name: string) => {
    if (name) renamePlaylist(id, name);
    setRenamingId(null);
  }, [renamePlaylist]);

  const handleAdd = useCallback((playlistId: string, result: SearchResult) => {
    addSong(playlistId, {
      title: result.title,
      video_url: result.video_url,
      duration: result.duration,
      thumbnail: result.thumbnail,
    });
  }, [addSong]);

  if (!open) return null;

  return (
    <Box
      ref={undefined as any}
      position="fixed"
      top="80px"
      right="20px"
      w="380px"
      maxH="80vh"
      bg="var(--sk-paper)"
      borderWidth="var(--sk-border)"
      borderColor="var(--sk-outline)"
      borderRadius="var(--sk-radius-card)"
      className="sk-settle"
      boxShadow="0 8px 32px rgba(0,0,0,0.6)"
      zIndex={2100}
      overflow="hidden"
      display="flex"
      flexDirection="column"
      userSelect="none"
      css={{ cursor: 'default' }}
    >
      {/* Header */}
      <Box
        position="relative"
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        px={4}
        py={3}
        borderBottomWidth="var(--sk-border)"
        borderColor="var(--sk-outline)"
        bg="var(--sk-paper-deep)"
      >
        <WashiTape color="var(--sk-repeat)" />
        <HStack gap={2}>
          <LuListMusic size={16} color="var(--sk-pencil)" />
          <Text fontSize="md" fontWeight="bold" color="var(--sk-ink)">
            Playlists
          </Text>
        </HStack>
        <IconButton
          aria-label="Close"
          size="2xs"
          variant="ghost"
          color="var(--sk-ink-faint)"
          _hover={{ bg: 'var(--sk-outline)', color: '#ffffff' }}
          onClick={onClose}
        >
          <LuX size={14} />
        </IconButton>
      </Box>

      <Box flex={1} overflowY="auto" px={4} py={3}>
        {loading ? (
          <Box display="flex" justifyContent="center" py={8}>
            <Spinner color="var(--sk-pencil)" size="md" />
          </Box>
        ) : selected ? (
          <>
            {/* Playlist detail header */}
            <HStack justify="space-between" mb={2}>
              <IconButton
                aria-label="Back"
                size="2xs"
                variant="ghost"
                color="var(--sk-ink-faint)"
                onClick={() => setSelectedId(null)}
              >
                <LuArrowLeft size={14} />
              </IconButton>
              <Box flex={1} minW={0}>
                {renamingId === selected.id ? (
                  <RenameRow
                    initial={selected.name}
                    onSave={(n) => handleRename(selected.id, n)}
                    onCancel={() => setRenamingId(null)}
                  />
                ) : (
                  <Text fontSize="sm" fontWeight="bold" color="var(--sk-ink)" textAlign="center" css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {selected.name}
                  </Text>
                )}
              </Box>
              <HStack gap={1}>
                {renamingId !== selected.id && (
                  <IconButton aria-label="Rename" size="2xs" variant="ghost" color="var(--sk-pencil-deep)" onClick={() => setRenamingId(selected.id)}>
                    <FiEdit2 size={12} />
                  </IconButton>
                )}
                <IconButton aria-label="Play all" size="2xs" variant="ghost" color="var(--sk-success)" onClick={() => playPlaylist(selected.id)}>
                  <LuPlay size={12} />
                </IconButton>
                <IconButton aria-label="Shuffle" size="2xs" variant="ghost" color="var(--sk-repeat)" onClick={() => playPlaylist(selected.id, true)}>
                  <LuShuffle size={12} />
                </IconButton>
                <IconButton aria-label="Delete" size="2xs" variant="ghost" color="var(--sk-danger)" onClick={() => deletePlaylist(selected.id)}>
                  <FiTrash2 size={12} />
                </IconButton>
              </HStack>
            </HStack>

            {/* Songs */}
            {selected.songs.length === 0 ? (
              <Text color="var(--sk-ink-dim)" textAlign="center" py={4} fontSize="sm">
                Belum ada lagu. Cari di bawah untuk menambahkan.
              </Text>
            ) : (
              <VStack gap={1.5} align="stretch" w="100%" mb={3}>
                {selected.songs.map((song) => (
                  <SongRow
                    key={song.id}
                    song={song}
                    onPlay={() => {
                      const idx = selected.songs.findIndex((s) => s.id === song.id);
                      playPlaylist(selected.id, false, idx);
                    }}
                    onRemove={() => removeSong(selected.id, song.id)}
                    onDownload={() => downloadSong(selected.id, song.video_url, song.title)}
                  />
                ))}
              </VStack>
            )}

            {/* Search to add */}
            <Box mt={2}>
              <Input
                size="xs"
                placeholder="Cari lagu di YouTube untuk ditambahkan..."
                value={query}
                onChange={(e) => handleSearch(e.target.value)}
                bg="var(--sk-paper-input)"
                borderColor="var(--sk-outline-soft)"
                color="var(--sk-ink)"
              />
            </Box>
            {searching && (
              <Box display="flex" justifyContent="center" py={4}>
                <Spinner color="var(--sk-pencil)" size="sm" />
              </Box>
            )}
            {!searching && searchResults.length > 0 && (
              <VStack gap={1.5} align="stretch" w="100%" mt={2}>
                {searchResults.map((r) => (
                  <HStack key={r.video_url} gap={2} w="100%" p={2} bg="var(--sk-paper-deep)" rounded="md" borderWidth="var(--sk-border)" borderColor="var(--sk-outline)">
                    <Box flex={1} minW={0}>
                      <Text fontSize="xs" color="var(--sk-ink)" css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.title}
                      </Text>
                      {formatDuration(r.duration) && (
                        <Text fontSize="10px" color="var(--sk-ink-dim)">{formatDuration(r.duration)}</Text>
                      )}
                    </Box>
                    <IconButton aria-label="Add" size="2xs" variant="ghost" color="var(--sk-success)" onClick={() => handleAdd(selected.id, r)}>
                      <LuPlus size={12} />
                    </IconButton>
                  </HStack>
                ))}
              </VStack>
            )}
          </>
        ) : (
          <>
            {/* Playlist list */}
            <HStack justify="space-between" mb={2}>
              <Text fontSize="xs" color="var(--sk-ink-faint)">Daftar playlist</Text>
              <CreatePlaylistRow onCreate={handleCreate} />
            </HStack>
            {playlists.length === 0 ? (
              <Text color="var(--sk-ink-dim)" textAlign="center" py={8} fontSize="sm">
                Belum ada playlist. Buat satu atau minta AI membuatkannya.
              </Text>
            ) : (
              <VStack gap={1.5} align="stretch" w="100%">
                {playlists.map((p) => (
                  <HStack
                    key={p.id}
                    gap={2}
                    w="100%"
                    p={2}
                    bg="var(--sk-paper-deep)"
                    rounded="md"
                    borderWidth="var(--sk-border)"
                    borderColor="var(--sk-outline)"
                    _hover={{ borderColor: 'var(--sk-outline-hover)' }}
                    cursor="pointer"
                    onClick={() => setSelectedId(p.id)}
                  >
                    <LuListMusic size={14} color="var(--sk-pencil)" />
                    <Box flex={1} minW={0}>
                      <Text fontSize="sm" color="var(--sk-ink)" css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.name}
                      </Text>
                      <Text fontSize="10px" color="var(--sk-ink-dim)">
                        {p.songs.length} lagu
                      </Text>
                    </Box>
                    <IconButton aria-label="Play" size="2xs" variant="ghost" color="var(--sk-success)" onClick={(e) => { e.stopPropagation(); playPlaylist(p.id); }}>
                      <LuPlay size={12} />
                    </IconButton>
                  </HStack>
                ))}
              </VStack>
            )}
          </>
        )}
      </Box>

      {/* Footer */}
      <Box
        px={4}
        py={2}
        borderTop="1px solid"
        borderColor="var(--sk-outline)"
        bg="var(--sk-paper-deep)"
      >
        <Text fontSize="10px" color="var(--sk-ink-mute)" textAlign="center">
          Kelola playlist lewat AI atau window ini
        </Text>
      </Box>
    </Box>
  );
}

export default PlaylistFloatingWindow;
