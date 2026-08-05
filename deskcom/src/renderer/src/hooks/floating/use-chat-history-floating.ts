import { useState, useCallback } from 'react';
import { useChatHistory } from '@/context/chat-history-context';
import { useWebSocket } from '@/context/websocket-context';

export function useChatHistoryFloating() {
  const {
    messages,
    historyList,
    currentHistoryUid,
    setHistoryList,
  } = useChatHistory();
  const { sendMessage } = useWebSocket();
  const [activeTab, setActiveTab] = useState<'history' | 'chat'>('chat');

  const createNewHistory = useCallback(() => {
    sendMessage({ type: 'create-new-history' });
  }, [sendMessage]);

  const fetchAndSetHistory = useCallback((uid: string) => {
    sendMessage({ type: 'fetch-and-set-history', history_uid: uid });
    setActiveTab('chat');
  }, [sendMessage]);

  const deleteHistory = useCallback((uid: string) => {
    sendMessage({ type: 'delete-history', history_uid: uid });
    setHistoryList((prev) => prev.filter((h) => h.uid !== uid));
  }, [sendMessage, setHistoryList]);

  return {
    messages,
    historyList,
    currentHistoryUid,
    activeTab,
    setActiveTab,
    fetchAndSetHistory,
    deleteHistory,
    createNewHistory,
  };
}
