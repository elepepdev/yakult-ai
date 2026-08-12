/* eslint-disable no-shadow */
// import { StrictMode } from 'react';
import { Box, ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { useEffect } from "react";
import { AiStateProvider } from "./context/ai-state-context";
import { Live2DConfigProvider } from "./context/live2d-config-context";
import { SubtitleProvider } from "./context/subtitle-context";
import { BgUrlProvider } from "./context/bgurl-context";
import WebSocketHandler from "./services/websocket-handler";
import { CameraProvider } from "./context/camera-context";
import { ChatHistoryProvider } from "./context/chat-history-context";
import { CharacterConfigProvider } from "./context/character-config-context";
import { Toaster } from "./components/ui/toaster";
import { VADProvider } from "./context/vad-context";
import { ModelRenderer } from "./components/canvas/ModelRenderer";
import ThoughtBubble from "./components/canvas/thought-bubble";
import { InputSubtitle } from "./components/electron/input-subtitle";
import { WebInputSubtitle } from "./components/web/web-input-subtitle";
import { ProactiveSpeakProvider } from "./context/proactive-speak-context";
import { ScreenCaptureProvider } from "./context/screen-capture-context";
// eslint-disable-next-line import/no-extraneous-dependencies, import/newline-after-import
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";

import { ModeProvider } from "./context/mode-context";
import { ThemeProvider } from "./context/theme-context";
import { GroupProvider } from "./context/group-context";
import { BrowserProvider } from "./context/browser-context";
import { AgentProviderConfigProvider } from "./context/agent-provider-config-context";
import { ConfigSchemaProvider } from "./context/config-schema-context";
import { MusicPlayerProvider } from "./context/music-player-context";
import MusicPlayerWindow from "./components/floating/music-player-window";
import MVWindow from "./components/floating/mv-window";
import { ErrorBoundary } from "./components/error-boundary";
import { useIpcHandlers } from "./hooks/utils/use-ipc-handlers";
import { useMode } from "./context/mode-context";
import { useWebSocket } from "./context/websocket-context";

import { StageLayoutProvider } from "./context/stage-layout-context";
import { StageQuickBar } from "./components/floating/stage-quick-bar";
import ApprovalFloatingWindow from "./components/floating/approval-floating-window";

function AppContent(): JSX.Element {
  useIpcHandlers();
  const { isElectron } = useMode();
  const { sendMessage } = useWebSocket();

  useEffect(() => {
    const handleResize = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    // Throttled user-activity signal so idle-life doesn't treat real input as idle
    let lastSent = 0;
    const THROTTLE_MS = 10_000;
    const notify = () => {
      const now = Date.now();
      if (now - lastSent < THROTTLE_MS) return;
      lastSent = now;
      sendMessage({ type: "user-active" });
    };
    window.addEventListener("pointermove", notify);
    window.addEventListener("pointerdown", notify);
    window.addEventListener("keydown", notify);
    return () => {
      window.removeEventListener("pointermove", notify);
      window.removeEventListener("pointerdown", notify);
      window.removeEventListener("keydown", notify);
    };
  }, [sendMessage]);

  return (
    <Box
      position="fixed"
      top={0}
      left={0}
      w="100vw"
      h="100vh"
      bg="transparent"
    >
      {/* Model canvas — full viewport so character is draggable anywhere */}
      <Box
        position="absolute"
        top={0}
        left={0}
        w="100vw"
        h="100vh"
        overflow="hidden"
      >
        <ModelRenderer />
      </Box>
      <ThoughtBubble />
      <StageQuickBar />
      {isElectron ? <InputSubtitle /> : <WebInputSubtitle />}
      <MusicPlayerWindow />
      <MVWindow />
      <ApprovalFloatingWindow />
    </Box>
  );
}

function App(): JSX.Element {
  return (
    <ChakraProvider value={defaultSystem}>
      <ModeProvider>
        <ThemeProvider>
          <AppWithGlobalStyles />
        </ThemeProvider>
      </ModeProvider>
    </ChakraProvider>
  );
}

function AppWithGlobalStyles(): JSX.Element {
  return (
    <ErrorBoundary>
      <CameraProvider>
        <ScreenCaptureProvider>
          <CharacterConfigProvider>
            <ChatHistoryProvider>
              <AiStateProvider>
                <ProactiveSpeakProvider>
                  <Live2DConfigProvider>
                    <SubtitleProvider>
                      <VADProvider>
                        <BgUrlProvider>
                          <GroupProvider>
                            <BrowserProvider>
                              <AgentProviderConfigProvider>
                                <ConfigSchemaProvider>
                                <MusicPlayerProvider>
                                  <StageLayoutProvider>
                                    <WebSocketHandler>
                                      <Toaster />
                                      <AppContent />
                                    </WebSocketHandler>
                                  </StageLayoutProvider>
                                </MusicPlayerProvider>
                                </ConfigSchemaProvider>
                              </AgentProviderConfigProvider>
                            </BrowserProvider>
                          </GroupProvider>
                        </BgUrlProvider>
                      </VADProvider>
                    </SubtitleProvider>
                  </Live2DConfigProvider>
                </ProactiveSpeakProvider>
              </AiStateProvider>
            </ChatHistoryProvider>
          </CharacterConfigProvider>
        </ScreenCaptureProvider>
      </CameraProvider>
    </ErrorBoundary>
  );
}

export default App;
