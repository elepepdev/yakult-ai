import { Box, Flex, IconButton, Spinner, Text } from '@chakra-ui/react';
import { LuFile, LuImage, LuX, LuPaperclip } from 'react-icons/lu';
import { Tooltip } from '@/components/ui/tooltip';
import type { AttachedFile } from '@/hooks/utils/use-file-attach';

interface Props {
  files: AttachedFile[];
  uploading: boolean;
  onPick: () => void;
  onRemove: (id: string) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFilesSelected: (files: FileList | null) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileAttachButton({ onPick, uploading }: Pick<Props, 'onPick' | 'uploading'>) {
  return (
    <Tooltip content="Attach file">
      <IconButton
        aria-label="Attach file"
        variant="ghost"
        color="#c0c0e0"
        size="xs"
        _hover={{ bg: 'var(--sk-outline)', color: '#ffffff' }}
        onClick={onPick}
        disabled={uploading}
      >
        {uploading ? <Spinner size="xs" /> : <LuPaperclip size={16} />}
      </IconButton>
    </Tooltip>
  );
}

export function FileAttachChips({ files, onRemove }: Pick<Props, 'files' | 'onRemove'>) {
  if (files.length === 0) return null;
  return (
    <Flex gap="1.5" flexWrap="wrap" px="2.5" pt="1.5">
      {files.map((f) => (
        <Flex
          key={f.id}
          align="center"
          gap="1"
          bg="var(--sk-paper-input)"
          border="1.5px solid"
          borderColor="var(--sk-outline-soft)"
          borderRadius="8px 6px 9px 5px"
          px="2"
          py="0.5"
          maxW="100%"
        >
          <Box color="#a0a0d0">
            {f.kind === 'image' ? <LuImage size={12} /> : <LuFile size={12} />}
          </Box>
          <Text
            fontSize="xs"
            color="#d0d0f0"
            css={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '160px' }}
          >
            {f.name}
          </Text>
          <Text fontSize="2xs" color="#7777aa">
            {formatSize(f.size)}
          </Text>
          <IconButton
            aria-label={`Remove ${f.name}`}
            variant="ghost"
            size="2xs"
            minW="auto"
            h="auto"
            p="0"
            color="#8888bb"
            _hover={{ color: '#ff8888' }}
            onClick={() => onRemove(f.id)}
          >
            <LuX size={10} />
          </IconButton>
        </Flex>
      ))}
    </Flex>
  );
}
