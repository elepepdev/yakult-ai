/* eslint-disable @typescript-eslint/ban-ts-comment */
import { useState, useCallback, useRef } from 'react';
import {
  Dialog,
  Box,
  Text,
  Button,
  Icon,
  Flex,
  Spinner,
} from '@chakra-ui/react';
import { LuUpload, LuFile, LuCheck, LuX } from 'react-icons/lu';
import { useWebSocket } from '@/context/websocket-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { toaster } from '@/components/ui/toaster';

interface VRMImportDialogProps {
  open: boolean;
  onClose: () => void;
}

export function VRMImportDialog({ open, onClose }: VRMImportDialogProps) {
  const { baseUrl, sendMessage } = useWebSocket();
  const { switchCharacter } = useSwitchCharacter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    modelName?: string;
    error?: string;
  } | null>(null);

  const reset = useCallback(() => {
    setFile(null);
    setDragOver(false);
    setUploading(false);
    setImportResult(null);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.toLowerCase().endsWith('.vrm')) {
      setFile(droppedFile);
      setImportResult(null);
    } else {
      toaster.create({
        title: 'Invalid file',
        description: 'Please drop a .vrm file',
        type: 'error',
        duration: 3000,
      });
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.name.toLowerCase().endsWith('.vrm')) {
        setFile(selectedFile);
        setImportResult(null);
      } else {
        toaster.create({
          title: 'Invalid file',
          description: 'Please select a .vrm file',
          type: 'error',
          duration: 3000,
        });
      }
    }
  }, []);

  const handleImport = useCallback(async () => {
    if (!file) return;

    setUploading(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${baseUrl}/models/import`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.success && data.model) {
        setImportResult({ success: true, modelName: data.model.name });
        toaster.create({
          title: 'VRM imported!',
          description: `Model "${data.model.name}" ready to use`,
          type: 'success',
          duration: 3000,
        });

        // Refresh config list so new model appears in dropdown
        sendMessage({ type: 'fetch-configs' });

        // Auto-select the model via generated config file
        if (data.config_file) {
          setTimeout(() => {
            switchCharacter(data.config_file);
            onClose();
            reset();
          }, 500);
        }
      } else {
        setImportResult({ success: false, error: data.error || 'Import failed' });
        toaster.create({
          title: 'Import failed',
          description: data.error || 'Unknown error',
          type: 'error',
          duration: 3000,
        });
      }
    } catch (error: any) {
      setImportResult({ success: false, error: error.message });
      toaster.create({
        title: 'Import error',
        description: error.message,
        type: 'error',
        duration: 3000,
      });
    } finally {
      setUploading(false);
    }
  }, [file, baseUrl, sendMessage, switchCharacter, onClose, reset]);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [onClose, reset]);

  return (
    <Dialog.Root open={open} onInteractOutside={handleClose}>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content
          bg="#1a1a2e"
          border="1px solid"
          borderColor="#2a2a4a"
          rounded="xl"
          boxShadow="0 8px 32px rgba(0,0,0,0.6)"
          maxW="480px"
        >
          <Dialog.Header borderBottom="1px solid" borderColor="#2a2a4a" px={5} py={4}>
            <Flex justify="space-between" align="center">
              <Text fontSize="md" fontWeight="bold" color="#e0e0ff">
                Import VRM Model
              </Text>
              <Button
                size="2xs"
                variant="ghost"
                color="#8888bb"
                _hover={{ bg: '#2a2a4a', color: '#fff' }}
                onClick={handleClose}
              >
                <LuX size={16} />
              </Button>
            </Flex>
          </Dialog.Header>

          <Dialog.Body px={5} py={5}>
            {/* Drop Zone */}
            <Box
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              border="2px dashed"
              borderColor={dragOver ? '#6666aa' : file ? '#3a3a6a' : '#2a2a4a'}
              bg={dragOver ? '#1a1a3e' : file ? '#1a1a2e' : 'transparent'}
              rounded="lg"
              p={8}
              textAlign="center"
              cursor="pointer"
              transition="all 0.2s"
              _hover={{ borderColor: '#5555aa', bg: '#15152a' }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".vrm"
                style={{ display: 'none' }}
                onChange={handleFileSelect}
              />

              {file ? (
                <Flex direction="column" align="center" gap={2}>
                  <Icon color="#6666aa" fontSize="2xl">
                    <LuFile />
                  </Icon>
                  <Text color="#c0c0e0" fontSize="sm" fontWeight="medium">
                    {file.name}
                  </Text>
                  <Text color="#666688" fontSize="xs">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </Text>
                </Flex>
              ) : (
                <Flex direction="column" align="center" gap={2}>
                  <Icon color="#555577" fontSize="3xl">
                    <LuUpload />
                  </Icon>
                  <Text color="#8888bb" fontSize="sm">
                    Drop a <strong>.vrm</strong> file here
                  </Text>
                  <Text color="#555577" fontSize="xs">
                    or click to browse
                  </Text>
                </Flex>
              )}
            </Box>

            {/* Import Result */}
            {importResult && (
              <Flex
                mt={4}
                p={3}
                rounded="md"
                bg={importResult.success ? '#0a2e1a' : '#2e0a0a'}
                align="center"
                gap={2}
              >
                <Icon
                  color={importResult.success ? '#44cc88' : '#cc4444'}
                  fontSize="md"
                >
                  {importResult.success ? <LuCheck /> : <LuX />}
                </Icon>
                <Text
                  color={importResult.success ? '#88ddbb' : '#dd8888'}
                  fontSize="sm"
                >
                  {importResult.success
                    ? `Model "${importResult.modelName}" imported! Switching...`
                    : importResult.error}
                </Text>
              </Flex>
            )}
          </Dialog.Body>

          <Dialog.Footer px={5} py={4} borderTop="1px solid" borderColor="#2a2a4a">
            <Flex justify="flex-end" gap={3}>
              <Button
                variant="ghost"
                color="#8888bb"
                _hover={{ bg: '#2a2a4a', color: '#e0e0ff' }}
                onClick={handleClose}
                disabled={uploading}
              >
                Cancel
              </Button>
              <Button
                bg="#4444aa"
                color="white"
                _hover={{ bg: '#5555bb' }}
                _disabled={{ bg: '#333366', opacity: 0.5 }}
                onClick={handleImport}
                disabled={!file || uploading}
              >
                {uploading ? (
                  <Flex align="center" gap={2}>
                    <Spinner size="sm" />
                    Importing...
                  </Flex>
                ) : (
                  'Import & Use'
                )}
              </Button>
            </Flex>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}

export default VRMImportDialog;
