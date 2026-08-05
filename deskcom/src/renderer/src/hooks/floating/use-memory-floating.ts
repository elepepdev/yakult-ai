import { useState, useCallback, useEffect } from 'react';
import { wsService } from '@/services/websocket-service';

export interface MemoryItem {
  id: string;
  fact: string;
  category: string;
  confidence: number;
  created_at: string;
  accessed_count: number;
}

export function useMemoryFloating() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const subscription = wsService.onMessage((message) => {
      if (message?.type === 'memories') {
        setMemories(message.data || []);
        setLoading(false);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const fetchMemories = useCallback(() => {
    setLoading(true);
    wsService.sendMessage({ type: 'fetch-memories' });
  }, []);

  const deleteMemory = useCallback((id: string) => {
    wsService.sendMessage({ type: 'delete-memory', id });
    setMemories((prev) => prev.filter((m) => m.id !== id));
  }, []);

  const updateMemory = useCallback((id: string, fact: string) => {
    wsService.sendMessage({ type: 'update-memory', id, fact });
    setMemories((prev) =>
      prev.map((m) => (m.id === id ? { ...m, fact } : m)),
    );
  }, []);

  return {
    memories,
    loading,
    fetchMemories,
    deleteMemory,
    updateMemory,
  };
}
