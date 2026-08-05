/* eslint-disable no-shadow */
/* eslint-disable no-underscore-dangle */
/* eslint-disable @typescript-eslint/ban-ts-comment */
import { memo, useRef, useEffect, useCallback } from "react";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { useInterrupt } from "@/hooks/utils/use-interrupt";
import { useAudioTask } from "@/hooks/utils/use-audio-task";
import { useLive2DModel } from "@/hooks/canvas/use-live2d-model";
import { useLive2DResize } from "@/hooks/canvas/use-live2d-resize";
import { useAiState, AiStateEnum } from "@/context/ai-state-context";
import { useLive2DExpression } from "@/hooks/canvas/use-live2d-expression";
import { useForceIgnoreMouse } from "@/hooks/utils/use-force-ignore-mouse";
import { getPlatform } from '@/platforms';

export const Live2D = memo(
  (): JSX.Element => {
    const { forceIgnoreMouse } = useForceIgnoreMouse();
    const { modelInfo } = useLive2DConfig();
    const internalContainerRef = useRef<HTMLDivElement>(null);
    const { aiState } = useAiState();
    const { resetExpression } = useLive2DExpression();

    const { canvasRef } = useLive2DResize({
      containerRef: internalContainerRef,
      modelInfo,
    });

    const { isDragging, handlers } = useLive2DModel({
      modelInfo,
      canvasRef,
    });

    useInterrupt();
    useAudioTask();

    useEffect(() => {
      if (aiState === AiStateEnum.IDLE) {
        const lappAdapter = (window as any).getLAppAdapter?.();
        if (lappAdapter) {
          resetExpression(lappAdapter, modelInfo);
        }
      }
    }, [aiState, modelInfo, resetExpression]);

    const handlePointerDown = (e: React.PointerEvent) => {
      handlers.onMouseDown(e);
    };

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
      const canvas = document.getElementById('canvas') as HTMLCanvasElement;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const relX = (e.clientX - rect.left) / rect.width;
      const relY = (e.clientY - rect.top) / rect.height;

      const viewX = (relX - 0.5) * 2;
      const viewY = (relY - 0.5) * -2;

      const adapter = (window as any).getLAppAdapter?.();
      adapter?.setCursorPosition?.(viewX, viewY);
    }, []);

    const handlePointerLeave = useCallback(() => {
      const adapter = (window as any).getLAppAdapter?.();
      adapter?.setCursorPosition?.(0, 0);
    }, []);

    const handleContextMenu = (e: React.MouseEvent) => {
      e.preventDefault();
      getPlatform().showContextMenu();
    };

    return (
      <div
        ref={internalContainerRef}
        id="live2d-internal-wrapper"
        style={{
          width: "100%",
          height: "100%",
          pointerEvents: forceIgnoreMouse ? "none" : "auto",
          overflow: "visible",
          position: "relative",
          cursor: isDragging ? "grabbing" : "default",
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        onContextMenu={handleContextMenu}
        {...handlers}
      >
        <canvas
          id="canvas"
          ref={canvasRef}
          style={{
            width: "100%",
            height: "100%",
            pointerEvents: forceIgnoreMouse ? "none" : "auto",
            display: "block",
            cursor: isDragging ? "grabbing" : "default",
          }}
        />
      </div>
    );
  },
);

Live2D.displayName = "Live2D";

export { useInterrupt, useAudioTask };
