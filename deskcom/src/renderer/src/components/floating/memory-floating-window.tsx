import {
  Box,
  Text,
  IconButton,
  Spinner,
  Input,
  Textarea,
  Badge,
  HStack,
  VStack,
} from '@chakra-ui/react';
import { useState, useMemo, useCallback, useEffect } from 'react';
import { LuX, LuSearch, LuBrain } from 'react-icons/lu';
import { FiTrash2, FiEdit2, FiCheck, FiX } from 'react-icons/fi';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { useMemoryFloating, MemoryItem } from '@/hooks/floating/use-memory-floating';

const CATEGORY_COLORS: Record<string, { bg: string; color: string }> = {
  preference: { bg: '#1a3a5c', color: '#88ccff' },
  personal: { bg: '#1a4a2e', color: '#88ffaa' },
  task: { bg: '#4a3a1a', color: '#ffcc66' },
  fact: { bg: '#3a1a4a', color: '#cc88ff' },
};

const CATEGORY_LABELS: Record<string, string> = {
  preference: 'Preference',
  personal: 'Personal',
  task: 'Task',
  fact: 'Fact',
};

function MemoryCard({
  item,
  onDelete,
  onUpdate,
}: {
  item: MemoryItem;
  onDelete: (id: string) => void;
  onUpdate: (id: string, fact: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(item.fact);

  const handleSave = useCallback(() => {
    if (editText.trim() && editText !== item.fact) {
      onUpdate(item.id, editText.trim());
    }
    setEditing(false);
  }, [editText, item.id, item.fact, onUpdate]);

  const handleCancel = useCallback(() => {
    setEditText(item.fact);
    setEditing(false);
  }, [item.fact]);

  const colors = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.fact;

  return (
    <Box
      p={3}
      bg="#16162a"
      rounded="lg"
      border="1px solid"
      borderColor="#2a2a4a"
      _hover={{ borderColor: '#4a4a7a' }}
      transition="border-color 0.15s"
      w="100%"
    >
      {editing ? (
        <VStack gap={2} align="stretch">
          <Textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            bg="#0d0d1a"
            border="1px solid"
            borderColor="#3a3a5a"
            color="#e0e0ff"
            fontSize="sm"
            minH="60px"
            resize="vertical"
            _focus={{ borderColor: '#6666cc' }}
          />
          <HStack gap={2} justify="flex-end">
            <IconButton
              aria-label="Save"
              size="2xs"
              variant="ghost"
              color="#88ffaa"
              _hover={{ bg: '#1a3a2e' }}
              onClick={handleSave}
            >
              <FiCheck size={14} />
            </IconButton>
            <IconButton
              aria-label="Cancel"
              size="2xs"
              variant="ghost"
              color="#ff8888"
              _hover={{ bg: '#3a1a1a' }}
              onClick={handleCancel}
            >
              <FiX size={14} />
            </IconButton>
          </HStack>
        </VStack>
      ) : (
        <>
          <HStack gap={2} mb={1.5} justify="space-between">
            <Badge
              bg={colors.bg}
              color={colors.color}
              px={2}
              py={0.5}
              rounded="md"
              fontSize="10px"
              fontWeight="medium"
              textTransform="uppercase"
              letterSpacing="0.5px"
            >
              {CATEGORY_LABELS[item.category] || item.category}
            </Badge>
            <HStack gap={1}>
              <IconButton
                aria-label="Edit"
                size="2xs"
                variant="ghost"
                color="#8888bb"
                _hover={{ bg: '#2a2a4a', color: '#ffffff' }}
                onClick={() => {
                  setEditText(item.fact);
                  setEditing(true);
                }}
              >
                <FiEdit2 size={12} />
              </IconButton>
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
          </HStack>
          <Text fontSize="sm" color="#c0c0e0" lineHeight="1.5">
            {item.fact}
          </Text>
          <HStack gap={3} mt={1.5}>
            <Text fontSize="10px" color="#666688">
              Confidence: {Math.round(item.confidence * 100)}%
            </Text>
            <Text fontSize="10px" color="#666688">
              Accessed: {item.accessed_count}x
            </Text>
          </HStack>
        </>
      )}
    </Box>
  );
}

interface MemoryFloatingWindowProps {
  open: boolean;
  onClose: () => void;
}

function MemoryFloatingWindow({ open, onClose }: MemoryFloatingWindowProps) {
  const { memories, loading, deleteMemory, updateMemory, fetchMemories } = useMemoryFloating();
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  // Fetch memories when the window opens
  useEffect(() => {
    if (open) {
      fetchMemories();
    }
  }, [open, fetchMemories]);

  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'memory-floating',
  });

  const filtered = useMemo(() => {
    let result = memories;
    if (categoryFilter) {
      result = result.filter((m) => m.category === categoryFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((m) => m.fact.toLowerCase().includes(q));
    }
    return result;
  }, [memories, searchQuery, categoryFilter]);

  const categories = useMemo(() => {
    const set = new Set(memories.map((m) => m.category));
    return Array.from(set);
  }, [memories]);

  if (!open) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      top="80px"
      right="20px"
      w="460px"
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
          <LuBrain size={16} color="#8888ff" />
          <Text fontSize="md" fontWeight="bold" color="#e0e0ff">
            Long-Term Memory
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

      {/* Search & Filter */}
      <Box px={4} py={3} borderBottom="1px solid" borderColor="#2a2a4a">
        <Box position="relative" mb={2}>
          <Box position="absolute" left={3} top="50%" transform="translateY(-50%)" color="#555588">
            <LuSearch size={14} />
          </Box>
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memories..."
            bg="#0d0d1a"
            border="1px solid"
            borderColor="#3a3a5a"
            color="#e0e0ff"
            pl={9}
            fontSize="sm"
            _focus={{ borderColor: '#6666cc' }}
          />
        </Box>
        <HStack gap={2} flexWrap="wrap">
          <Badge
            px={2.5}
            py={1}
            rounded="md"
            fontSize="11px"
            cursor="pointer"
            bg={categoryFilter === null ? '#4444aa' : '#2a2a4a'}
            color={categoryFilter === null ? '#ffffff' : '#8888bb'}
            onClick={() => setCategoryFilter(null)}
            _hover={{ bg: categoryFilter === null ? '#5555bb' : '#3a3a5a' }}
            transition="background 0.15s"
            userSelect="none"
          >
            All
          </Badge>
          {categories.map((cat) => (
            <Badge
              key={cat}
              px={2.5}
              py={1}
              rounded="md"
              fontSize="11px"
              cursor="pointer"
              bg={categoryFilter === cat ? '#4444aa' : '#2a2a4a'}
              color={categoryFilter === cat ? '#ffffff' : '#8888bb'}
              onClick={() => setCategoryFilter(cat === categoryFilter ? null : cat)}
              _hover={{ bg: categoryFilter === cat ? '#5555bb' : '#3a3a5a' }}
              transition="background 0.15s"
              userSelect="none"
            >
              {CATEGORY_LABELS[cat] || cat}
            </Badge>
          ))}
        </HStack>
      </Box>

      {/* Memory List */}
      <Box flex={1} overflowY="auto" px={4} py={3}>
        {loading ? (
          <Box display="flex" justifyContent="center" py={8}>
            <Spinner color="#8888ff" size="md" />
          </Box>
        ) : filtered.length === 0 ? (
          <Text color="#666688" textAlign="center" py={8} fontSize="sm">
            {memories.length === 0
              ? 'No memories yet. Start a conversation to build long-term memory.'
              : 'No memories match your filter.'}
          </Text>
        ) : (
          <VStack gap={3} align="stretch" w="100%">
            {filtered.map((item) => (
              <MemoryCard
                key={item.id}
                item={item}
                onDelete={deleteMemory}
                onUpdate={updateMemory}
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
          {memories.length} memory fact{memories.length !== 1 ? 's' : ''} stored
        </Text>
      </Box>
    </Box>
  );
}

export default MemoryFloatingWindow;
