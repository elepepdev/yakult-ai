import { useEffect, useState } from 'react';

/**
 * Track the VRM character's projected head screen position (canvas px),
 * broadcast by useVRM every frame. Returns null until the model is loaded.
 * Used to anchor the chat bubble above the character's head.
 */
export function useVrmHeadPosition(): { x: number; y: number } | null {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && typeof detail.x === 'number') {
        setPos({ x: detail.x, y: detail.y });
      }
    };
    window.addEventListener('vrm-head-screen-position', handler as EventListener);
    return () => window.removeEventListener('vrm-head-screen-position', handler as EventListener);
  }, []);
  return pos;
}
