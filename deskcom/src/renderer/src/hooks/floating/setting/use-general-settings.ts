import { useCallback } from 'react';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useBgUrl } from '@/context/bgurl-context';
import { useSubtitle } from '@/context/subtitle-context';

const LANGUAGE_KEY = 'language';
const IMAGE_COMPRESSION_QUALITY_KEY = 'imageCompressionQuality';
const IMAGE_MAX_WIDTH_KEY = 'imageMaxWidth';
const GRID_SPEC_KEY = 'gridSpec';

export function useGeneralSettings() {
  const { wsUrl: ctxWsUrl, setWsUrl: setCtxWsUrl, baseUrl: ctxBaseUrl, setBaseUrl: setCtxBaseUrl, sendMessage } = useWebSocket();
  const { confName, configFiles, setConfName } = useConfig();
  const { backgroundUrl, setBackgroundUrl, useCameraBackground, setUseCameraBackground } = useBgUrl();
  const { showSubtitle, setShowSubtitle } = useSubtitle();

  const [language, setLanguage] = useLocalStorage(LANGUAGE_KEY, 'en');
  const [imageCompressionQuality, setImageCompressionQualityState] = useLocalStorage(IMAGE_COMPRESSION_QUALITY_KEY, 0.7);
  const [imageMaxWidth, setImageMaxWidthState] = useLocalStorage(IMAGE_MAX_WIDTH_KEY, 800);
  const [gridSpec, setGridSpecState] = useLocalStorage(GRID_SPEC_KEY, '8x6');

  const setImageCompressionQuality = useCallback((val: number) => {
    setImageCompressionQualityState(val);
    localStorage.setItem(IMAGE_COMPRESSION_QUALITY_KEY, String(val));
  }, [setImageCompressionQualityState]);

  const setImageMaxWidth = useCallback((val: number) => {
    setImageMaxWidthState(val);
    localStorage.setItem(IMAGE_MAX_WIDTH_KEY, String(val));
  }, [setImageMaxWidthState]);

  const setGridSpec = useCallback((val: string) => {
    setGridSpecState(val);
    sendMessage({ type: 'set-grid-spec', grid_spec: val });
  }, [setGridSpecState, sendMessage]);

  return {
    language,
    setLanguage,
    showSubtitle,
    setShowSubtitle,
    useCameraBg: useCameraBackground,
    setUseCameraBg: setUseCameraBackground,
    backgroundUrl,
    setBackgroundUrl,
    confName,
    configFiles,
    setConfName,
    wsUrl: ctxWsUrl,
    setWsUrl: setCtxWsUrl,
    baseUrl: ctxBaseUrl,
    setBaseUrl: setCtxBaseUrl,
    imageCompressionQuality,
    setImageCompressionQuality,
    imageMaxWidth,
    setImageMaxWidth,
    gridSpec,
    setGridSpec,
  };
}
