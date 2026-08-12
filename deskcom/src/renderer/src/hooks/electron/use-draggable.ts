import { useState, useRef, useEffect, useCallback } from 'react';
import { useStageLayout } from '@/context/stage-layout-context';
import { calculateSnapPosition } from './use-smart-snap';

interface Position {
  x: number;
  y: number;
}

interface UseDraggableProps {
  componentId: string;
  defaultPosition?: Position;
}

export function useDraggable({ componentId, defaultPosition = { x: 20, y: 80 } }: UseDraggableProps) {
  const [isDragging, setIsDragging] = useState(false);
  const positionRef = useRef<Position>(defaultPosition);
  const dragStartRef = useRef<Position>({ x: 0, y: 0 });
  const domRef = useRef<HTMLDivElement | null>(null);

  const {
    snapToGrid,
    updateWindowPosition,
    getWindowPosition,
    registerWindowRect,
    unregisterWindowRect,
    getAllOtherWindowRects,
  } = useStageLayout();

  // Apply saved position whenever the element attaches. A plain effect is not
  // enough: windows mount later than the provider, so at effect time the ref is
  // null and the transform would never be applied, leaving positionRef stale.
  const elementRef = useCallback(
    (el: HTMLDivElement | null) => {
      domRef.current = el;
      if (el) {
        const savedPos = getWindowPosition(componentId);
        if (savedPos) {
          positionRef.current = savedPos;
          el.style.transform = `translate(${savedPos.x}px, ${savedPos.y}px)`;
        }
      }
    },
    [componentId, getWindowPosition],
  );

  // Update rect registry when component renders / resizes
  const updateRectRegistry = useCallback(() => {
    const el = domRef.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      registerWindowRect(componentId, {
        x: positionRef.current.x,
        y: positionRef.current.y,
        width: rect.width,
        height: rect.height,
      });
    }
  }, [componentId, registerWindowRect]);

  useEffect(() => {
    updateRectRegistry();
    return () => unregisterWindowRect(componentId);
  }, [componentId, updateRectRegistry, unregisterWindowRect]);

  const handleMouseDown = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (
      target.tagName === 'INPUT'
      || target.tagName === 'TEXTAREA'
      || target.tagName === 'BUTTON'
      || target.closest('button')
      || target.closest('input')
      || target.closest('textarea')
    ) {
      return;
    }

    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX - positionRef.current.x,
      y: e.clientY - positionRef.current.y,
    };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const el = domRef.current;
      if (!el) return;

      let rawX = moveEvent.clientX - dragStartRef.current.x;
      let rawY = moveEvent.clientY - dragStartRef.current.y;

      if (snapToGrid) {
        const rect = el.getBoundingClientRect();
        const otherRects = getAllOtherWindowRects(componentId);
        const snapped = calculateSnapPosition(
          { x: rawX, y: rawY },
          { width: rect.width, height: rect.height },
          otherRects,
        );
        rawX = snapped.x;
        rawY = snapped.y;
      }

      positionRef.current = { x: rawX, y: rawY };
      el.style.transform = `translate(${rawX}px, ${rawY}px)`;
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      updateWindowPosition(componentId, positionRef.current);
      updateRectRegistry();

      document.removeEventListener('mousemove', handleMouseMove, true);
      document.removeEventListener('mouseup', handleMouseUp, true);
    };

    document.addEventListener('mousemove', handleMouseMove, true);
    document.addEventListener('mouseup', handleMouseUp, true);
  };

  return {
    elementRef,
    isDragging,
    handleMouseDown,
  };
}
