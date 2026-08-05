import { useLive2DConfig } from '@/context/live2d-config-context';

export function useLive2dSettings() {
  const { modelInfo, setModelInfo } = useLive2DConfig();

  const setPointerInteractive = (val: boolean) => {
    if (modelInfo) {
      setModelInfo({ ...modelInfo, pointerInteractive: val });
    }
  };

  const setScrollToResize = (val: boolean) => {
    if (modelInfo) {
      setModelInfo({ ...modelInfo, scrollToResize: val });
    }
  };

  return {
    pointerInteractive: modelInfo?.pointerInteractive !== false,
    setPointerInteractive,
    scrollToResize: modelInfo?.scrollToResize === true,
    setScrollToResize,
  };
}
