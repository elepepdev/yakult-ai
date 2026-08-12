/* eslint-disable no-sparse-arrays */
/* eslint-disable react-hooks/exhaustive-deps */
// eslint-disable-next-line object-curly-newline
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { wsService, MessageEvent } from '@/services/websocket-service';
import {
  WebSocketContext, HistoryInfo, defaultWsUrl, defaultBaseUrl,
} from '@/context/websocket-context';
import { ModelInfo, useLive2DConfig } from '@/context/live2d-config-context';
import { useSubtitle } from '@/context/subtitle-context';
import { audioTaskQueue } from '@/utils/task-queue';
import { useAudioTask } from '@/components/canvas/live2d';
import { useBgUrl } from '@/context/bgurl-context';
import { useConfig } from '@/context/character-config-context';
import { useChatHistory } from '@/context/chat-history-context';
import { toaster } from '@/components/ui/toaster';
import { useVAD } from '@/context/vad-context';
import { AiState, useAiState } from "@/context/ai-state-context";
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { getPlatform } from '@/platforms';
import { useGroup } from '@/context/group-context';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useBrowser } from '@/context/browser-context';
import { useAgentProviderConfig } from '@/context/agent-provider-config-context';
import { useConfigSchema } from '@/context/config-schema-context';

function WebSocketHandler({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const [wsState, setWsState] = useState<string>('CLOSED');
  const [wsUrl, setWsUrl] = useLocalStorage<string>('wsUrl', defaultWsUrl);
  const [baseUrl, setBaseUrl] = useLocalStorage<string>('baseUrl', defaultBaseUrl);
  const [aiMode] = useLocalStorage<string>('aiMode', 'full_agent');
  const { aiState, setAiState, backendSynthComplete, setBackendSynthComplete } = useAiState();
  const { modelInfo, setModelInfo } = useLive2DConfig();
  const { setSubtitleText, setSubconsciousText } = useSubtitle();
  const { clearResponse, setForceNewMessage, appendHumanMessage, appendOrUpdateToolCallMessage, appendYoutubeInvite } = useChatHistory();
  const { addAudioTask } = useAudioTask();
  const bgUrlContext = useBgUrl();
  const { confUid, setConfName, setConfUid, setConfigFiles } = useConfig();
  const [pendingModelInfo, setPendingModelInfo] = useState<ModelInfo | undefined>(undefined);
  const { setSelfUid, setGroupMembers, setIsOwner } = useGroup();
  const { startMic, stopMic, autoStartMicOnConvEnd } = useVAD();
  const autoStartMicOnConvEndRef = useRef(autoStartMicOnConvEnd);
  const { interrupt } = useInterrupt();
  const { setBrowserViewData } = useBrowser();
  const { setAgentConfig, setAvailableModels } = useAgentProviderConfig();
  const { setSchema } = useConfigSchema();
  const modelInfoRef = useRef(modelInfo);
  modelInfoRef.current = modelInfo;
  const aiStateRef = useRef(aiState);
  aiStateRef.current = aiState;

  useEffect(() => {
    autoStartMicOnConvEndRef.current = autoStartMicOnConvEnd;
  }, [autoStartMicOnConvEnd]);

  useEffect(() => {
    if (pendingModelInfo && confUid) {
      setModelInfo(pendingModelInfo);
      setPendingModelInfo(undefined);
    }
  }, [pendingModelInfo, setModelInfo, confUid]);

  const {
    setCurrentHistoryUid, setMessages, setHistoryList,
  } = useChatHistory();

  const handleControlMessage = useCallback((controlText: string) => {
    switch (controlText) {
      case 'start-mic':
        console.log('Starting microphone...');
        startMic();
        break;
      case 'stop-mic':
        console.log('Stopping microphone...');
        stopMic();
        break;
      case 'conversation-chain-start':
        setAiState('thinking-speaking');
        setSubconsciousText('');
        audioTaskQueue.clearQueue();
        clearResponse();
        break;
      case 'conversation-chain-end':
        audioTaskQueue.addTask(() => new Promise<void>((resolve) => {
          setAiState((currentState: AiState) => {
            if (currentState === 'thinking-speaking') {
              // Auto start mic if enabled
              if (autoStartMicOnConvEndRef.current) {
                startMic();
              }
              return 'idle';
            }
            return currentState;
          });
          resolve();
        }));
        break;
      case 'backend-restarting':
        console.log('Backend is restarting...');
        toaster.create({
          title: 'Restarting...',
          description: 'Backend is restarting. Frontend will reload shortly.',
          type: 'info',
          duration: 3000,
        });
        break;
      default:
        console.warn('Unknown control command:', controlText);
    }
  }, [setAiState, clearResponse, setForceNewMessage, startMic, stopMic]);

  const handleWebSocketMessage = useCallback((message: MessageEvent) => {
    console.log('Received message from server:', message);
    switch (message.type) {
      case 'control':
        if (message.text) {
          handleControlMessage(message.text);
        }
        break;
      case 'set-model-and-conf':
        setAiState('loading');
        if (message.conf_name) {
          setConfName(message.conf_name);
        }
        if (message.conf_uid) {
          setConfUid(message.conf_uid);
          console.log('confUid', message.conf_uid);
        }
        if (message.client_uid) {
          setSelfUid(message.client_uid);
        }
        if (message.agent_config) {
          setAgentConfig(message.agent_config);
        }

        // Attach model_type from WebSocket message to model_info
        if (message.model_info && message.model_info.url) {
          if (message.model_type) {
            message.model_info.type = message.model_type;
          }
          if (!message.model_info.url.startsWith("http")) {
            message.model_info.url = baseUrl + message.model_info.url;
          }
        }

        setPendingModelInfo(message.model_info);
        setAiState('idle');
        break;
      case 'clear-subconscious':
        setSubconsciousText('');
        break;
      case 'full-text':
        if (message.subconscious && message.text) {
          // Only show subconscious bubble when AI is strictly idle
          if (aiStateRef.current === 'idle') {
            setSubconsciousText(message.text);
          }
        } else if (message.text) {
          setSubtitleText(message.text);
        }
        break;
      case 'config-files':
        if (message.configs) {
          setConfigFiles(message.configs);
        }
        break;
      case 'config-schema':
        if (message.schema) {
          setSchema(message.schema);
        }
        break;
      case 'config-saved':
        if (message.agent_config) {
          setAgentConfig(message.agent_config);
        }
        if (message.schema) {
          setSchema(message.schema);
        }
        if (message.restart_required) {
          toaster.create({
            title: t('notification.restartRequired'),
            type: 'warning',
            duration: 6000,
          });
        } else {
          toaster.create({
            title: message.message || t('notification.configSaved'),
            type: 'success',
            duration: 2000,
          });
        }
        break;
      case 'available-models':
        if (Array.isArray(message.models)) {
          setAvailableModels(message.models);
        }
        break;

      case 'config-switched':
        setAiState('idle');
        setSubtitleText(t('notification.characterLoaded'));

        toaster.create({
          title: t('notification.characterSwitched'),
          type: 'success',
          duration: 2000,
        });

        // setModelInfo(undefined);

        wsService.sendMessage({ type: 'fetch-history-list' });
        wsService.sendMessage({ type: 'create-new-history' });
        wsService.sendMessage({ type: 'fetch-config-schema', lang: 'en' });
        break;
      case 'background-files':
        if (message.files) {
          bgUrlContext?.setBackgroundFiles(message.files);
        }
        break;
      case 'audio':
        if (aiState === 'interrupted' || aiState === 'listening') {
          console.log('Audio playback intercepted. Sentence:', message.display_text?.text);
        } else {
          console.log("actions", message.actions);
          addAudioTask({
            audioBase64: message.audio || '',
            volumes: message.volumes || [],
            sliceLength: message.slice_length || 0,
            displayText: message.display_text || null,
            expressions: message.actions?.expressions || null,
            forwarded: message.forwarded || false,
          });
        }
        break;
      case 'history-data':
        if (message.messages) {
          setMessages(message.messages);
        }
        toaster.create({
          title: t('notification.historyLoaded'),
          type: 'success',
          duration: 2000,
        });
        break;
      case 'new-history-created':
        setAiState('idle');
        setSubtitleText(t('notification.newConversation'));
        // No need to open mic here
        if (message.history_uid) {
          setCurrentHistoryUid(message.history_uid);
          setMessages([]);
          const newHistory: HistoryInfo = {
            uid: message.history_uid,
            latest_message: null,
            timestamp: new Date().toISOString(),
          };
          setHistoryList((prev: HistoryInfo[]) => [newHistory, ...prev]);
          toaster.create({
            title: t('notification.newChatHistory'),
            type: 'success',
            duration: 2000,
          });
        }
        break;
      case 'history-deleted':
        toaster.create({
          title: message.success
            ? t('notification.historyDeleteSuccess')
            : t('notification.historyDeleteFail'),
          type: message.success ? 'success' : 'error',
          duration: 2000,
        });
        break;
      case 'history-list':
        if (message.histories) {
          setHistoryList(message.histories);
          if (message.histories.length > 0) {
            setCurrentHistoryUid(message.histories[0].uid);
          }
        }
        break;
      case 'user-input-transcription':
        console.log('user-input-transcription: ', message.text);
        setSubconsciousText('');
        if (message.text) {
          appendHumanMessage(message.text);
        }
        break;
      case 'model-emotions-updated':
        if (message.emotionMap && modelInfoRef.current) {
          console.log('Emotion map auto-updated from VRM expressions:', message.emotionMap);
          setModelInfo({ ...modelInfoRef.current, emotionMap: message.emotionMap });
        }
        break;
      case 'error':
        toaster.create({
          title: message.message,
          type: 'error',
          duration: 2000,
        });
        break;
      case 'group-update':
        console.log('Received group-update:', message.members);
        if (message.members) {
          setGroupMembers(message.members);
        }
        if (message.is_owner !== undefined) {
          setIsOwner(message.is_owner);
        }
        break;
      case 'group-operation-result':
        toaster.create({
          title: message.message,
          type: message.success ? 'success' : 'error',
          duration: 2000,
        });
        break;
      case 'backend-synth-complete':
        setBackendSynthComplete(true);
        break;
      case 'conversation-chain-end':
        if (!audioTaskQueue.hasTask()) {
          setAiState((currentState: AiState) => {
            if (currentState === 'thinking-speaking') {
              return 'idle';
            }
            return currentState;
          });
        }
        break;
      case 'ai-mode-updated':
        // Confirmation that the backend switched AI mode
        console.log('AI mode updated:', message.mode);
        break;
      case 'force-new-message':
        setForceNewMessage(true);
        break;
      case 'interrupt-signal':
        // Handle forwarded interrupt
        interrupt(false); // do not send interrupt signal to server
        break;
      case 'tool_call_status':
        if (message.tool_id && message.tool_name && message.status) {
          // Auto-toggle passthrough for click tools (pet mode fix)
          const CLICK_TOOLS = ['click', 'x11_click', 'type_text', 'click_element', 'click_window'];
          if (CLICK_TOOLS.includes(message.tool_name)) {
            if (message.status === 'running') {
              getPlatform().setIgnoreMouseEvents(true);
            } else if (message.status === 'completed' || message.status === 'error') {
              getPlatform().setIgnoreMouseEvents(false);
            }
          }

          // If there's browser view data included, store it in the browser context
          if (message.browser_view) {
            console.log('Browser view data received:', message.browser_view);
            setBrowserViewData(message.browser_view);
          }

          appendOrUpdateToolCallMessage({
            id: message.tool_id,
            type: 'tool_call_status',
            role: 'ai',
            tool_id: message.tool_id,
            tool_name: message.tool_name,
            name: message.name,
            status: message.status as ('running' | 'completed' | 'error'),
            content: message.content || '',
            timestamp: message.timestamp || new Date().toISOString(),
            progress: message.progress ?? null,
          });
        } else {
          console.warn('Received incomplete tool_call_status message:', message);
        }
        break;
      case 'youtube-invite':
        appendYoutubeInvite({
          title: message.title || '',
          stream_url: message.stream_url || '',
          request_id: message.request_id || message.tool_id || '',
        });
        break;
      case 'play-vrma':
        window.dispatchEvent(new CustomEvent('vrm-play-vrma', {
          detail: { animation: message.animation },
        }));
        break;
      case 'hide-pet':
        getPlatform().hidePet();
        break;
      default:
        console.warn('Unknown message type:', message.type);
    }
  }, [aiState, addAudioTask, appendHumanMessage, appendYoutubeInvite, baseUrl, bgUrlContext, setAiState, setConfName, setConfUid, setConfigFiles, setCurrentHistoryUid, setHistoryList, setMessages, setModelInfo, setSubtitleText, startMic, stopMic, setSelfUid, setGroupMembers, setIsOwner, setSubconsciousText, backendSynthComplete, setBackendSynthComplete, clearResponse, handleControlMessage, appendOrUpdateToolCallMessage, interrupt, setBrowserViewData, t]);

  useEffect(() => {
    wsService.connect(wsUrl);
  }, [wsUrl]);

  useEffect(() => {
    const stateSubscription = wsService.onStateChange(setWsState);
    const messageSubscription = wsService.onMessage(handleWebSocketMessage);
    return () => {
      stateSubscription.unsubscribe();
      messageSubscription.unsubscribe();
    };
  }, [wsUrl, handleWebSocketMessage]);

  // --- Sync saved AI mode on reconnect ---
  useEffect(() => {
    if (wsState === 'OPEN') {
      wsService.sendMessage({ type: 'set-ai-mode', mode: aiMode });
      wsService.sendMessage({ type: 'fetch-config-schema', lang: 'en' });
    }
  }, [wsState]);

  // --- VRM Expression Auto-Discovery ---
  // When the VRM model loads, it dispatches a CustomEvent with all available
  // expressions. We forward them to the backend which auto-updates model_dict.json
  // and re-sends the updated emotionMap.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.expressions && wsService.getCurrentState() === 'OPEN') {
        wsService.sendMessage({
          type: 'discover-vrm-expressions',
          expressions: detail.expressions,
        });
      }
    };
    window.addEventListener('vrm-expressions-discovered', handler);
    return () => window.removeEventListener('vrm-expressions-discovered', handler);
  }, [wsState]);

  const webSocketContextValue = useMemo(() => ({
    sendMessage: wsService.sendMessage.bind(wsService),
    wsState,
    reconnect: () => wsService.connect(wsUrl),
    wsUrl,
    setWsUrl,
    baseUrl,
    setBaseUrl,
  }), [wsState, wsUrl, baseUrl]);

  return (
    <WebSocketContext.Provider value={webSocketContextValue}>
      {children}
    </WebSocketContext.Provider>
  );
}

export default WebSocketHandler;
