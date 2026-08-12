import {
  Box,
  Text,
  IconButton,
  Button,
  HStack,
  VStack,
  Tag,
} from '@chakra-ui/react';
import { useMemo } from 'react';
import { LuX, LuFilePen, LuTrash2, LuShieldAlert, LuFileText } from 'react-icons/lu';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { useApprovalFloating, ApprovalRequest } from '@/hooks/floating/use-approval-floating';
import { useTranslation } from 'react-i18next';

const ACCENT = '#1a1a2e';
const ACCENT_HEADER = '#16162a';
const OUTLINE = '#2a2a4a';

function DiffView({ diff }: { diff: string }) {
  const lines = useMemo(() => diff.split('\n'), [diff]);

  return (
    <Box
      bg="#0d0d1a"
      border="1px solid"
      borderColor={OUTLINE}
      rounded="md"
      p={3}
      maxH="300px"
      overflowY="auto"
      fontFamily="monospace"
      fontSize="11px"
      lineHeight="1.6"
      css={{
        '&::-webkit-scrollbar': { width: '6px' },
        '&::-webkit-scrollbar-track': { background: 'transparent' },
        '&::-webkit-scrollbar-thumb': { background: '#2a2a4a', borderRadius: '3px' },
      }}
    >
      {lines.map((line, i) => {
        let color = '#c0c0d8';
        if (line.startsWith('+++') || line.startsWith('---')) color = '#8a8ac0';
        else if (line.startsWith('@@')) color = '#79c0ff';
        else if (line.startsWith('+')) color = '#7ee787';
        else if (line.startsWith('-')) color = '#ff7b72';
        return (
          <Box key={i} whiteSpace="pre" color={color}>
            {line || ' '}
          </Box>
        );
      })}
    </Box>
  );
}

function formatSize(bytes?: number): string {
  if (bytes === undefined || bytes === null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ApprovalCard({ request, onRespond }: {
  request: ApprovalRequest;
  onRespond: (approvalId: string, approved: boolean) => void;
}) {
  const { t } = useTranslation();
  const isDelete = request.operation === 'delete';

  return (
    <Box
      w="520px"
      maxH="70vh"
      bg={ACCENT}
      border="1px solid"
      borderColor={isDelete ? '#5a2a3a' : '#3a4a5a'}
      rounded="xl"
      boxShadow="0 8px 32px rgba(0,0,0,0.7)"
      overflow="hidden"
      display="flex"
      flexDirection="column"
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
        borderColor={OUTLINE}
        bg={ACCENT_HEADER}
      >
        <HStack gap={2}>
          <LuShieldAlert size={18} color={isDelete ? '#ff7b72' : '#f0b429'} />
          <Text fontSize="md" fontWeight="bold" color="#e0e0ff">
            {t('approval.title')}
          </Text>
        </HStack>
        <HStack gap={1}>
          <Tag.Root
            size="sm"
            colorScheme={isDelete ? 'red' : 'orange'}
            variant="subtle"
          >
            <Tag.Label fontSize="10px">
              {isDelete ? t('approval.delete') : t('approval.write')}
            </Tag.Label>
          </Tag.Root>
          <IconButton
            aria-label="Deny"
            size="2xs"
            variant="ghost"
            color="#8888bb"
            _hover={{ bg: '#2a2a4a', color: '#ffffff' }}
            onClick={() => onRespond(request.approval_id, false)}
          >
            <LuX size={14} />
          </IconButton>
        </HStack>
      </Box>

      {/* Body */}
      <Box flex={1} overflowY="auto" px={5} py={4} spaceY={4}>
        <VStack align="stretch" gap={3}>
          <Box>
            <Text fontSize="xs" color="#8888bb" mb={1}>
              {t('approval.tool')}
            </Text>
            <HStack gap={2}>
              {isDelete
                ? <LuTrash2 size={16} color="#ff7b72" />
                : <LuFilePen size={16} color="#f0b429" />}
              <Text fontSize="sm" color="#e0e0ff" fontWeight="semibold">
                {request.tool_name}
              </Text>
            </HStack>
          </Box>

          <Box>
            <Text fontSize="xs" color="#8888bb" mb={1}>
              {t('approval.path')}
            </Text>
            <Box
              bg="#0d0d1a"
              border="1px solid"
              borderColor={OUTLINE}
              rounded="md"
              px={3}
              py={2}
              fontFamily="monospace"
              fontSize="12px"
              color="#79c0ff"
              wordBreak="break-all"
            >
              {request.path}
            </Box>
          </Box>

          {isDelete ? (
            <Box
              bg="#2a1218"
              border="1px solid"
              borderColor="#5a2a3a"
              rounded="md"
              px={3}
              py={2.5}
            >
              <Text fontSize="sm" color="#ffb4ae">
                <LuTrash2 size={13} style={{ display: 'inline', marginRight: 6 }} />
                {request.is_dir
                  ? t('approval.deleteDirWarning')
                  : t('approval.deleteFileWarning')}
              </Text>
              {(request.is_dir || (request.size ?? 0) > 0) && (
                <Text fontSize="xs" color="#c96a6a" mt={1}>
                  {request.is_dir
                    ? `${t('approval.recursiveNote')} · `
                    : ''}
                  {t('approval.size')}: {formatSize(request.size)}
                </Text>
              )}
            </Box>
          ) : (
            <Box>
              <HStack gap={2} mb={1}>
                <LuFileText size={13} color="#8888bb" />
                <Text fontSize="xs" color="#8888bb">
                  {request.exists ? t('approval.diffHint') : t('approval.newFileHint')}
                </Text>
              </HStack>
              {request.diff ? (
                <DiffView diff={request.diff} />
              ) : (
                <Text fontSize="sm" color="#666688">
                  {t('approval.noDiff')}
                </Text>
              )}
            </Box>
          )}

          {request.content_preview && (
            <Box>
              <Text fontSize="xs" color="#8888bb" mb={1}>
                {t('approval.contentPreview')}
              </Text>
              <Box
                bg="#0d0d1a"
                border="1px solid"
                borderColor={OUTLINE}
                rounded="md"
                px={3}
                py={2}
                maxH="120px"
                overflowY="auto"
                fontFamily="monospace"
                fontSize="11px"
                color="#c0c0d8"
                whiteSpace="pre-wrap"
                wordBreak="break-word"
              >
                {request.content_preview}
              </Box>
            </Box>
          )}
        </VStack>
      </Box>

      {/* Footer */}
      <Box
        px={5}
        py={3}
        borderTop="1px solid"
        borderColor={OUTLINE}
        bg={ACCENT_HEADER}
      >
        <HStack gap={3} justify="flex-end">
          <Button
            size="sm"
            variant="outline"
            borderColor="#5a3a3a"
            color="#ff8a8a"
            bg="transparent"
            _hover={{ bg: '#3a1a1a', borderColor: '#ff7b72' }}
            onClick={() => onRespond(request.approval_id, false)}
          >
            {t('approval.deny')}
          </Button>
          <Button
            size="sm"
            colorScheme={isDelete ? 'red' : 'green'}
            onClick={() => onRespond(request.approval_id, true)}
          >
            {isDelete ? t('approval.confirmDelete') : t('approval.approve')}
          </Button>
        </HStack>
      </Box>
    </Box>
  );
}

function ApprovalFloatingWindow() {
  const { current, pendingCount, respond } = useApprovalFloating();
  const { elementRef, isDragging, handleMouseDown } = useDraggable({
    componentId: 'approval-floating',
  });

  if (!current) return null;

  return (
    <Box
      ref={elementRef}
      position="fixed"
      top="70px"
      right="20px"
      zIndex={2100}
      onMouseDown={handleMouseDown}
      cursor={isDragging ? 'grabbing' : 'default'}
    >
      <ApprovalCard request={current} onRespond={respond} />
      {pendingCount > 1 && (
        <Box
          mt={2}
          textAlign="center"
          fontSize="xs"
          color="#8888bb"
          bg="rgba(26,26,46,0.9)"
          rounded="md"
          py={1}
        >
          +{pendingCount - 1} {pendingCount - 1 === 1 ? 'pending request' : 'pending requests'}
        </Box>
      )}
    </Box>
  );
}

export default ApprovalFloatingWindow;
