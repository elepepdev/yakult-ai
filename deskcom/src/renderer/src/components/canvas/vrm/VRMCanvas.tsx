/* eslint-disable no-shadow */
/* eslint-disable @typescript-eslint/ban-ts-comment */
import { memo, useRef, useEffect, useCallback } from 'react';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { useForceIgnoreMouse } from '@/hooks/utils/use-force-ignore-mouse';

import { useVRM } from '@/hooks/canvas/useVRM';
import { getPlatform } from '@/platforms';

export const VRMCanvas = memo(
  (): JSX.Element => {
    const { forceIgnoreMouse } = useForceIgnoreMouse();
    const { modelInfo } = useLive2DConfig();
    const { aiState } = useAiState();
    const internalContainerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const hoverSentRef = useRef(false);

    const {
      isLoaded,
      setExpression,
      setExpressions,
      resetExpression,
      openEyes,
      startLipSync,
      stopLipSync,
      playVRMA,
      setRandomPoseEnabled,
      resize,
      pointerHandlers,
      setCursorPosition,
      isDragging,
    } = useVRM({ modelInfo, canvasRef });

    // Listen for audio task events dispatched by useAudioTask hook
    useEffect(() => {
      if (!isLoaded) return;

      const handleVrmAudioTask = (e: CustomEvent) => {
        const { expressions } = e.detail || {};

        if (expressions && expressions.length > 0) {
          const exprNames = expressions.map((expr: unknown) => typeof expr === 'string' ? expr : String(expr));
          setExpressions(exprNames);
        }
      };

      const handleLipSyncStart = (e: CustomEvent) => {
        const { audio, volumes, sliceLength } = e.detail || {};
        if (audio && volumes && volumes.length > 0) {
          startLipSync(audio, volumes, sliceLength || 20);
        }
      };

      const handleLipSyncStop = () => {
        stopLipSync();
      };

      window.addEventListener('vrm-audio-task', handleVrmAudioTask as EventListener);
      window.addEventListener('vrm-lip-sync-start', handleLipSyncStart as EventListener);
      window.addEventListener('vrm-lip-sync-stop', handleLipSyncStop as EventListener);

      const handlePlayVrma = (e: CustomEvent) => {
        const { animation } = e.detail || {};
        if (animation) {
          playVRMA(animation);
        }
      };
      window.addEventListener('vrm-play-vrma', handlePlayVrma as EventListener);

      return () => {
        window.removeEventListener('vrm-audio-task', handleVrmAudioTask as EventListener);
        window.removeEventListener('vrm-lip-sync-start', handleLipSyncStart as EventListener);
        window.removeEventListener('vrm-lip-sync-stop', handleLipSyncStop as EventListener);
        window.removeEventListener('vrm-play-vrma', handlePlayVrma as EventListener);
      };
    }, [isLoaded, setExpression, startLipSync, stopLipSync, playVRMA]);

    // Hold the last emotion a few seconds after the AI finishes speaking, then
    // ease back to neutral (a real person's mood lingers before fading). Reset
    // immediately when the user starts talking (listening) so the character
    // looks attentive rather than stuck in the previous mood.
    useEffect(() => {
      if (!isLoaded) return;
      if (aiState === AiStateEnum.IDLE) {
        // Open the eyes immediately when the AI finishes speaking, keeping the
        // emotion until the delayed reset below fades back to neutral.
        openEyes();
        const timer = setTimeout(() => {
          resetExpression();
          stopLipSync();
        }, 5000);
        return () => clearTimeout(timer);
      }
      if (aiState === AiStateEnum.LISTENING) {
        resetExpression();
        stopLipSync();
      }
    }, [aiState, isLoaded, resetExpression, stopLipSync, openEyes]);

    // Enable random pose animations only while the AI is fully idle
    useEffect(() => {
      setRandomPoseEnabled(aiState === AiStateEnum.IDLE);
    }, [aiState, setRandomPoseEnabled]);

    // Handle resize
    useEffect(() => {
      const handleResizeEvent = () => {
        resize();
      };

      window.addEventListener('resize', handleResizeEvent);
      return () => window.removeEventListener('resize', handleResizeEvent);
    }, [resize]);

    // Initial resize after model loads
    useEffect(() => {
      if (isLoaded) {
        setTimeout(resize, 100);
      }
    }, [isLoaded, resize]);

    // Hover tracking for mouse passthrough
    useEffect(() => {
      const container = internalContainerRef.current;
      if (!container) return;

      const onMouseEnter = () => {
        hoverSentRef.current = true;
        getPlatform().updateComponentHover('vrm-model', true);
      };
      const onMouseLeave = () => {
        hoverSentRef.current = false;
        getPlatform().updateComponentHover('vrm-model', false);
      };

      container.addEventListener('mouseenter', onMouseEnter);
      container.addEventListener('mouseleave', onMouseLeave);
      return () => {
        container.removeEventListener('mouseenter', onMouseEnter);
        container.removeEventListener('mouseleave', onMouseLeave);
        if (hoverSentRef.current) {
          getPlatform().updateComponentHover('vrm-model', false);
        }
      };
    }, []);

    // When passthrough is on, the window ignores pointer events, so the normal
    // onPointerMove handler never fires. The main process instead polls the global
    // cursor (screen.getCursorScreenPoint) and pushes screen coords here. Convert
    // them to canvas-relative view coords (-1..1) and feed the head-follow.
    useEffect(() => {
      if (!forceIgnoreMouse) return;

      return getPlatform().onCursorScreenPosition((screenX, screenY) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const canvasLeft = rect.left + (window.screenX || 0);
        const canvasTop = rect.top + (window.screenY || 0);
        const relX = (screenX - canvasLeft) / rect.width;
        const relY = (screenY - canvasTop) / rect.height;
        setCursorPosition((relX - 0.5) * 2, (relY - 0.5) * -2);
      });
    }, [forceIgnoreMouse, setCursorPosition]);

    const handleContextMenu = useCallback((e: React.MouseEvent) => {
      e.preventDefault();
      getPlatform().showContextMenu();
    }, []);

    const handlePointerDown = useCallback((e: React.PointerEvent) => {
      pointerHandlers.onPointerDown(e);
    }, [pointerHandlers]);

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
      const canvas = canvasRef.current;
      if (canvas) {
        const rect = canvas.getBoundingClientRect();
        const relX = (e.clientX - rect.left) / rect.width;
        const relY = (e.clientY - rect.top) / rect.height;
        setCursorPosition((relX - 0.5) * 2, (relY - 0.5) * -2);
      }
      pointerHandlers.onPointerMove(e);
    }, [pointerHandlers, setCursorPosition]);

    const handlePointerUp = useCallback((e: React.PointerEvent) => {
      pointerHandlers.onPointerUp(e);
    }, [pointerHandlers]);

    const handlePointerLeave = useCallback(() => {
      setCursorPosition(0, 0);
    }, [setCursorPosition]);

    return (
      <div
        ref={internalContainerRef}
        style={{
          width: '100%',
          height: '100%',
          overflow: 'visible',
          position: 'relative',
          pointerEvents: forceIgnoreMouse ? 'none' : 'auto',
          cursor: isDragging ? 'grabbing' : 'default',
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onContextMenu={handleContextMenu}
      >
        <canvas
          ref={canvasRef}
          id="vrm-canvas"
          style={{
            width: '100%',
            height: '100%',
            display: 'block',
            pointerEvents: forceIgnoreMouse ? 'none' : 'auto',
            cursor: isDragging ? 'grabbing' : 'default',
          }}
        />
        {!isLoaded && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              color: 'var(--sk-pencil)',
              fontSize: '14px',
              fontFamily: 'var(--sk-font-body)',
              textAlign: 'center',
            }}
          >
            Loading VRM...
          </div>
        )}
      </div>
    );
  },
);

VRMCanvas.displayName = 'VRMCanvas';

export default VRMCanvas;
