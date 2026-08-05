import { useEffect, useCallback, useRef } from 'react';
import { useInterrupt } from './use-interrupt';
import { useMicToggle } from './use-mic-toggle';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { useForceIgnoreMouse } from '@/hooks/utils/use-force-ignore-mouse';
import { toaster } from '@/components/ui/toaster';
import { getPlatform } from '@/platforms';
import { useWebSocket } from '@/context/websocket-context';

export function useIpcHandlers() {
  const { handleMicToggle } = useMicToggle();
  const { interrupt } = useInterrupt();
  const { modelInfo, setModelInfo } = useLive2DConfig();
  const { switchCharacter } = useSwitchCharacter();
  const { setForceIgnoreMouse } = useForceIgnoreMouse();
  const { sendMessage } = useWebSocket();

  // Use ref to avoid useCallback dependency on modelInfo (which changes frequently).
  // This prevents the entire effect from re-registering all listeners on every modelInfo change.
  const modelInfoRef = useRef(modelInfo);
  modelInfoRef.current = modelInfo;

  const micToggleHandler = useCallback(() => {
    handleMicToggle();
  }, [handleMicToggle]);

  const interruptHandler = useCallback(() => {
    interrupt();
  }, [interrupt]);

  const scrollToResizeHandler = useCallback(() => {
    const current = modelInfoRef.current;
    if (current) {
      setModelInfo({
        ...current,
        scrollToResize: !current.scrollToResize,
      });
    }
  }, [setModelInfo]);

  const switchCharacterHandler = useCallback(
    (filename: string) => {
      switchCharacter(filename);
    },
    [switchCharacter],
  );

  const forceIgnoreMouseChangedHandler = useCallback(
    (isForced: boolean) => {
      console.log('Force ignore mouse changed:', isForced);
      setForceIgnoreMouse(isForced);
      toaster.create({
        title: isForced ? 'Passthrough: ON' : 'Passthrough: OFF',
        description: isForced
          ? 'Clicks pass through the window. Press F8 or use tray menu to toggle.'
          : 'Mouse interaction enabled. Press F8 or use tray menu to toggle.',
        type: isForced ? 'info' : 'success',
        duration: 3000,
      });
    },
    [setForceIgnoreMouse],
  );

  const toggleForceIgnoreMouseHandler = useCallback(() => {
    getPlatform().toggleForceIgnoreMouse();
  }, []);

  const restartAppHandler = useCallback(() => {
    // Notify backend to restart
    sendMessage({ type: 'restart-backend' });
    // Reload frontend after a short delay to allow backend to restart
    setTimeout(() => {
      window.location.reload();
    }, 2000);
  }, [sendMessage]);

  useEffect(() => {
    const unlisteners: (() => void)[] = [];

    unlisteners.push(getPlatform().onMicToggle(micToggleHandler));
    unlisteners.push(getPlatform().onInterrupt(interruptHandler));
    unlisteners.push(getPlatform().onToggleScrollToResize(scrollToResizeHandler));
    unlisteners.push(getPlatform().onSwitchCharacter(switchCharacterHandler));
    unlisteners.push(getPlatform().onToggleForceIgnoreMouse(toggleForceIgnoreMouseHandler));
    unlisteners.push(getPlatform().onForceIgnoreMouseChanged(forceIgnoreMouseChangedHandler));
    unlisteners.push(getPlatform().onRestartApp(restartAppHandler));

    return () => {
      unlisteners.forEach((fn) => fn());
    };
  }, [
    micToggleHandler,
    interruptHandler,
    scrollToResizeHandler,
    switchCharacterHandler,
    toggleForceIgnoreMouseHandler,
    forceIgnoreMouseChangedHandler,
    restartAppHandler,
  ]);
}
