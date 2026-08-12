import { useState, useRef } from 'react';
import { useWebSocket } from '@/context/websocket-context';
import { useAiState } from '@/context/ai-state-context';
import { useInterrupt } from '@/components/canvas/live2d';
import { useChatHistory } from '@/context/chat-history-context';
import { useVAD } from '@/context/vad-context';
import { useMediaCapture } from '@/hooks/utils/use-media-capture';
import { useFileAttach } from '@/hooks/utils/use-file-attach';
import { useMention } from './use-mention';
import { getPlatform } from '@/platforms';

const MENTION_RE = /@(\S+)/g;

async function resolveFileContexts(text: string): Promise<string> {
  const mentions: string[] = [];
  let match: RegExpExecArray | null;
  const re = new RegExp(MENTION_RE.source, 'g');
  while ((match = re.exec(text)) !== null) {
    mentions.push(match[1]);
  }
  if (mentions.length === 0) return text;

  const fileBlocks: string[] = [];
  let resolvedText = text;
  for (const filePath of mentions) {
    try {
      const result = await getPlatform().readFile(filePath);
      if (result.success && result.content) {
        fileBlocks.push(`\n--- File: ${filePath} ---\n${result.content}\n---`);
        resolvedText = resolvedText.replace(`@${filePath}`, filePath);
      }
    } catch {
      // File not found — leave @ in text (might be email, etc.)
    }
  }

  if (fileBlocks.length > 0) {
    resolvedText += '\n\n' + fileBlocks.join('\n');
  }
  return resolvedText;
}

export function useTextInput() {
  const [inputText, setInputText] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const wsContext = useWebSocket();
  const { aiState } = useAiState();
  const { interrupt } = useInterrupt();
  const { appendHumanMessage } = useChatHistory();
  const { stopMic, autoStopMic } = useVAD();
  const { captureAllMedia } = useMediaCapture();
  const attach = useFileAttach();

  const mention = useMention(inputText, setInputText, inputRef);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(e.target.value);
  };

  const handleSelect = (e: React.SyntheticEvent<HTMLInputElement>) => {
    mention.cursorRef.current = (e.target as HTMLInputElement).selectionStart || 0;
  };

  const handleSend = async () => {
    if ((!inputText.trim() && attach.files.length === 0) || !wsContext) return;
    if (aiState === 'thinking-speaking') {
      interrupt();
    }

    const images = await captureAllMedia();

    const resolvedText = await resolveFileContexts(inputText.trim());

    const filePayload = attach.files.map((f) => ({
      name: f.name,
      mime_type: f.mime_type,
      kind: f.kind,
      data: f.data,
      size: f.size,
    }));

    appendHumanMessage(resolvedText);
    wsContext.sendMessage({
      type: 'text-input',
      text: resolvedText,
      images,
      files: filePayload.length > 0 ? filePayload : undefined,
    });

    if (autoStopMic) stopMic();
    setInputText('');
    attach.clearFiles();
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (isComposing) return;

    if (mention.handleKeyDown(e)) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCompositionStart = () => setIsComposing(true);
  const handleCompositionEnd = () => setIsComposing(false);

  return {
    inputText,
    setInputText: handleInputChange,
    handleSend,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleSelect,
    inputRef,
    mention,
    attach,
  };
}
