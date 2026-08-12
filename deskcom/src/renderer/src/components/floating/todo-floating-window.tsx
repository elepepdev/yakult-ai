import {
  Box,
  Text,
  IconButton,
  Spinner,
  HStack,
  VStack,
} from '@chakra-ui/react';
import { useMemo, useEffect } from 'react';
import { LuX, LuBell } from 'react-icons/lu';
import { FiTrash2 } from 'react-icons/fi';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { useTodoFloating, TodoItem } from '@/hooks/floating/use-todo-floating';
import { WashiTape } from '@/components/ui/washi-tape';
import { SketchCheckbox } from '@/components/ui/sketch-checkbox';

function formatDatetime(dt: string | null): string {
  if (!dt) return '';
  try {
    const d = new Date(dt);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (isToday) return `Today ${time}`;
    const date = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    return `${date} ${time}`;
  } catch {
    return dt;
  }
}

function isOverdue(dt: string | null): boolean {
  if (!dt) return false;
  try {
    return new Date(dt) < new Date();
  } catch {
    return false;
  }
}

function TodoCard({
  item,
  onDelete,
  onToggle,
}: {
  item: TodoItem;
  onDelete: (id: string) => void;
  onToggle: (id: string, completed: boolean) => void;
}) {
  const overdue = !item.completed && isOverdue(item.datetime);

  return (
    <Box
      p={3}
      bg="#16162a"
      rounded="lg"
      border="1px solid"
      borderColor={overdue ? '#5a2a2a' : '#2a2a4a'}
      _hover={{ borderColor: overdue ? '#8a3a3a' : '#4a4a7a' }}
      transition="border-color 0.15s"
      w="100%"
      opacity={item.completed ? 0.5 : 1}
    >
      <HStack gap={3} align="flex-start">
        <Checkbox.Root
          checked={item.completed}
          onCheckedChange={(e) => onToggle(item.id, !!e.checked)}
          mt={0.5}
          colorPalette="green"
        >
          <Checkbox.HiddenInput />
          <Checkbox.Control borderColor="#4a4a6a" />
        </Checkbox.Root>
        <Box flex={1} minW={0}>
          <Text
            fontSize="sm"
            color={item.completed ? '#666688' : '#e0e0ff'}
            textDecoration={item.completed ? 'line-through' : 'none'}
            lineHeight="1.5"
            wordBreak="break-word"
          >
            {item.text}
          </Text>
          {item.datetime && (
            <Text
              fontSize="10px"
              color={overdue ? '#ff6666' : '#666688'}
              mt={0.5}
            >
              {overdue ? 'Overdue: ' : ''}{formatDatetime(item.datetime)}
            </Text>
          )}
        </Box>
        <IconButton
          aria-label="Delete"
          size="2xs"
          variant="ghost"
          color="#ff6666"
          _hover={{ bg: '#3a1a1a' }}
          onClick={() => onDelete(item.id)}
        >
          <FiTrash2 size={12} />
        </IconButton>
      </HStack>
    </Box>
  );
}

interface TodoFloatingWindowProps {
  open: boolean;
  onClose: () => void;
}

function TodoFloatingWindow({ open, onClose }: TodoFloatingWindowProps) {
  const { todos, loading, fetchTodos, deleteTodo, toggleTodo } = useTodoFloating();

  useEffect(() => {
    if (open) {
      fetchTodos();
    }
  }, [open, fetchTodos]);

  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'todo-floating',
  });

  const sorted = useMemo(() => {
    const incomplete = todos.filter((t) => !t.completed);
    const complete = todos.filter((t) => t.completed);
    incomplete.sort((a, b) => {
      if (a.datetime && b.datetime) return new Date(a.datetime).getTime() - new Date(b.datetime).getTime();
      if (a.datetime) return -1;
      if (b.datetime) return 1;
      return 0;
    });
    return [...incomplete, ...complete];
  }, [todos]);

  if (!open) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      top="80px"
      left="20px"
      w="380px"
      maxH="80vh"
      bg="#1a1a2e"
      border="1px solid"
      borderColor="#2a2a4a"
      rounded="xl"
      boxShadow="0 8px 32px rgba(0,0,0,0.6)"
      zIndex={2000}
      overflow="hidden"
      display="flex"
      flexDirection="column"
      onMouseDown={handleMouseDown}
      cursor={isDragging ? 'grabbing' : 'default'}
      userSelect="none"
    >
      {/* Header */}
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
        <HStack gap={2}>
          <LuBell size={16} color="#8888ff" />
          <Text fontSize="md" fontWeight="bold" color="#e0e0ff">
            Reminders
          </Text>
        </HStack>
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

      {/* Todo List */}
      <Box flex={1} overflowY="auto" px={4} py={3}>
        {loading ? (
          <Box display="flex" justifyContent="center" py={8}>
            <Spinner color="#8888ff" size="md" />
          </Box>
        ) : sorted.length === 0 ? (
          <Text color="#666688" textAlign="center" py={8} fontSize="sm">
            No reminders yet. Ask the AI to set a reminder for you.
          </Text>
        ) : (
          <VStack gap={3} align="stretch" w="100%">
            {sorted.map((item) => (
              <TodoCard
                key={item.id}
                item={item}
                onDelete={deleteTodo}
                onToggle={toggleTodo}
              />
            ))}
          </VStack>
        )}
      </Box>

      {/* Footer */}
      <Box
        px={4}
        py={2.5}
        borderTop="1px solid"
        borderColor="#2a2a4a"
        bg="#16162a"
      >
        <Text fontSize="10px" color="#555577" textAlign="center">
          {todos.filter((t) => !t.completed).length} pending &middot; {todos.filter((t) => t.completed).length} completed
        </Text>
      </Box>
    </Box>
  );
}

export default TodoFloatingWindow;
