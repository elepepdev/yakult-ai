import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';

export type LayoutPreset = 'compact' | 'focus' | 'studio' | 'custom';

export interface WindowRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface WindowPositionMap {
  [componentId: string]: { x: number; y: number };
}

interface StageLayoutContextType {
  preset: LayoutPreset;
  snapToGrid: boolean;
  setPreset: (preset: LayoutPreset) => void;
  setSnapToGrid: (enable: boolean) => void;
  windowPositions: WindowPositionMap;
  updateWindowPosition: (componentId: string, pos: { x: number; y: number }) => void;
  getWindowPosition: (componentId: string) => { x: number; y: number } | undefined;
  registerWindowRect: (componentId: string, rect: WindowRect) => void;
  unregisterWindowRect: (componentId: string) => void;
  getAllOtherWindowRects: (excludeId: string) => WindowRect[];
  applyPreset: (preset: LayoutPreset) => void;
}

const STORAGE_KEY_PRESET = 'stage_layout_preset';
const STORAGE_KEY_POSITIONS = 'stage_layout_positions';
const STORAGE_KEY_SNAP = 'stage_layout_snap';

const StageLayoutContext = createContext<StageLayoutContextType | null>(null);

export function StageLayoutProvider({ children }: { children: React.ReactNode }) {
  const [preset, setPresetState] = useState<LayoutPreset>(() => {
    return (localStorage.getItem(STORAGE_KEY_PRESET) as LayoutPreset) || 'focus';
  });

  const [snapToGrid, setSnapToGridState] = useState<boolean>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_SNAP);
    return saved !== null ? saved === 'true' : true;
  });

  const [windowPositions, setWindowPositions] = useState<WindowPositionMap>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_POSITIONS);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const windowRectsRef = React.useRef<{ [componentId: string]: WindowRect }>({});

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_PRESET, preset);
  }, [preset]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_SNAP, String(snapToGrid));
  }, [snapToGrid]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_POSITIONS, JSON.stringify(windowPositions));
  }, [windowPositions]);

  const setSnapToGrid = useCallback((enable: boolean) => {
    setSnapToGridState(enable);
  }, []);

  const updateWindowPosition = useCallback((componentId: string, pos: { x: number; y: number }) => {
    setWindowPositions((prev) => ({
      ...prev,
      [componentId]: pos,
    }));
  }, []);

  const getWindowPosition = useCallback((componentId: string) => {
    return windowPositions[componentId];
  }, [windowPositions]);

  const registerWindowRect = useCallback((componentId: string, rect: WindowRect) => {
    windowRectsRef.current[componentId] = rect;
  }, []);

  const unregisterWindowRect = useCallback((componentId: string) => {
    delete windowRectsRef.current[componentId];
  }, []);

  const getAllOtherWindowRects = useCallback((excludeId: string): WindowRect[] => {
    return Object.entries(windowRectsRef.current)
      .filter(([id]) => id !== excludeId)
      .map(([, rect]) => rect);
  }, []);

  const applyPreset = useCallback((newPreset: LayoutPreset) => {
    setPresetState(newPreset);
    if (newPreset === 'compact') {
      // Hide or reset floating windows to corner
      const newPos: WindowPositionMap = {
        'chat-history-floating': { x: -9999, y: -9999 },
        'music-player': { x: -9999, y: -9999 },
        'todo-floating': { x: -9999, y: -9999 },
        'memory-floating': { x: -9999, y: -9999 },
      };
      setWindowPositions(newPos);
    } else if (newPreset === 'focus') {
      // Clean sidebar layout
      const newPos: WindowPositionMap = {
        'chat-history-floating': { x: 20, y: 80 },
        'music-player': { x: 20, y: 480 },
        'todo-floating': { x: -9999, y: -9999 },
        'memory-floating': { x: -9999, y: -9999 },
      };
      setWindowPositions(newPos);
    } else if (newPreset === 'studio') {
      // Full dashboard layout
      const newPos: WindowPositionMap = {
        'chat-history-floating': { x: 20, y: 80 },
        'music-player': { x: 460, y: 80 },
        'todo-floating': { x: 460, y: 380 },
        'memory-floating': { x: 900, y: 80 },
      };
      setWindowPositions(newPos);
    }
  }, []);

  const setPreset = useCallback((p: LayoutPreset) => {
    applyPreset(p);
  }, [applyPreset]);

  const value = useMemo(
    () => ({
      preset,
      snapToGrid,
      setPreset,
      setSnapToGrid,
      windowPositions,
      updateWindowPosition,
      getWindowPosition,
      registerWindowRect,
      unregisterWindowRect,
      getAllOtherWindowRects,
      applyPreset,
    }),
    [
      preset,
      snapToGrid,
      setPreset,
      setSnapToGrid,
      windowPositions,
      updateWindowPosition,
      getWindowPosition,
      registerWindowRect,
      unregisterWindowRect,
      getAllOtherWindowRects,
      applyPreset,
    ],
  );

  return (
    <StageLayoutContext.Provider value={value}>
      {children}
    </StageLayoutContext.Provider>
  );
}

export function useStageLayout() {
  const context = useContext(StageLayoutContext);
  if (!context) {
    throw new Error('useStageLayout must be used within a StageLayoutProvider');
  }
  return context;
}
