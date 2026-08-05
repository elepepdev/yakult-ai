import { useState, useCallback, useEffect } from 'react';
import { wsService } from '@/services/websocket-service';

export interface TodoItem {
  id: string;
  text: string;
  datetime: string | null;
  completed: boolean;
  created_at: string;
}

export function useTodoFloating() {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const subscription = wsService.onMessage((message) => {
      if (message?.type === 'todos') {
        setTodos(message.data || []);
        setLoading(false);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const fetchTodos = useCallback(() => {
    setLoading(true);
    wsService.sendMessage({ type: 'fetch-todos' });
  }, []);

  const addTodo = useCallback((text: string, datetime?: string) => {
    wsService.sendMessage({ type: 'add-todo', text, datetime });
  }, []);

  const deleteTodo = useCallback((id: string) => {
    wsService.sendMessage({ type: 'delete-todo', id });
    setTodos((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toggleTodo = useCallback((id: string, completed: boolean) => {
    wsService.sendMessage({ type: 'update-todo', id, completed });
    setTodos((prev) =>
      prev.map((t) => (t.id === id ? { ...t, completed } : t)),
    );
  }, []);

  return {
    todos,
    loading,
    fetchTodos,
    addTodo,
    deleteTodo,
    toggleTodo,
  };
}
