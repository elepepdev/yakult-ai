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
import { InputSubtitle } from "./components/electron/input-subtitle";
import { WebInputSubtitle } from "./components/web/web-input-subtitle";
import { ProactiveSpeakProvider } from "./context/proactive-speak-context";
import { ScreenCaptureProvider } from "./context/screen-capture-context";
// eslint-disable-next-line import/no-extraneous-dependencies, import/newline-after-import
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";

import { ModeProvider } from "./context/mode-context";
import { GroupProvider } from "./context/group-context";
import { BrowserProvider } from "./context/browser-context";
import { AgentProviderConfigProvider } from "./context/agent-provider-config-context";
import { MusicPlayerProvider } from "./context/music-player-context";
import MusicPlayerWindow from "./components/floating/music-player-window";
import { ErrorBoundary } from "./components/error-boundary";
import { useIpcHandlers } from "./hooks/utils/use-ipc-handlers";
import { useMode } from "./context/mode-context";

function AppContent(): JSX.Element {
  useIpcHandlers();
  const { isElectron } = useMode();

  useEffect(() => {
    const handleResize = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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
      {isElectron ? <InputSubtitle /> : <WebInputSubtitle />}
      <MusicPlayerWindow />
    </Box>
  );
}

function App(): JSX.Element {
  return (
    <ChakraProvider value={defaultSystem}>
      <ModeProvider>
        <AppWithGlobalStyles />
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
                                <MusicPlayerProvider>
                                  <WebSocketHandler>
                                    <Toaster />
                                    <AppContent />
                                  </WebSocketHandler>
                                </MusicPlayerProvider>
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
