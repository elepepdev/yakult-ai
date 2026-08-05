import {
  createContext, useContext, useState, useMemo,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useConfig } from '@/context/character-config-context';

/**
 * Model emotion mapping interface
 * @interface EmotionMap
 */
interface EmotionMap {
  [key: string]: number | string;
}

/**
 * Motion weight mapping interface
 * @interface MotionWeightMap
 */
export interface MotionWeightMap {
  [key: string]: number;
}

/**
 * Tap motion mapping interface
 * @interface TapMotionMap
 */
export interface TapMotionMap {
  [key: string]: MotionWeightMap;
}

/**
 * Viseme mapping for VRM lip-sync
 * @interface VisemeMap
 */
export interface VisemeMap {
  aa?: string;
  ee?: string;
  ih?: string;
  oh?: string;
  ou?: string;
}

/**
 * Character model information interface
 * Supports both Live2D and VRM (VRoid) models
 * @interface ModelInfo
 */
export interface ModelInfo {
  /** Model name */
  name?: string;

  /** Model description */
  description?: string;

  /** Model type: 'live2d' or 'vrm' */
  type?: string;

  /** Model URL (Live2D .model3.json or VRM .vrm file) */
  url: string;

  /** Scale factor (Live2D) */
  kScale: number;

  /** Initial X position shift (Live2D) */
  initialXshift: number;

  /** Initial Y position shift (Live2D) */
  initialYshift: number;

  /** Idle motion group name (Live2D) */
  idleMotionGroupName?: string;

  /** Default emotion */
  defaultEmotion?: number | string;

  /** Emotion mapping configuration */
  emotionMap: EmotionMap;

  /** Viseme mapping for VRM lip-sync */
  visemeMap?: VisemeMap;

  /** Enable pointer interactivity */
  pointerInteractive?: boolean;

  /** Tap motion mapping configuration (Live2D) */
  tapMotions?: TapMotionMap;

  /** Enable scroll to resize */
  scrollToResize?: boolean;

  /** Initial scale */
  initialScale?: number;
}

/**
 * Live2D configuration context state interface
 * @interface Live2DConfigState
 */
interface Live2DConfigState {
  modelInfo?: ModelInfo;
  setModelInfo: (info: ModelInfo | undefined) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

/**
 * Default values and constants
 */
const DEFAULT_CONFIG = {
  modelInfo: {
    scrollToResize: true,
  } as ModelInfo | undefined,
  isLoading: false,
};

/**
 * Create the Live2D configuration context
 */
export const Live2DConfigContext = createContext<Live2DConfigState | null>(null);

/**
 * Live2D Configuration Provider Component
 * @param {Object} props - Provider props
 * @param {React.ReactNode} props.children - Child components
 */
export function Live2DConfigProvider({ children }: { children: React.ReactNode }) {
  const { confUid: _confUid } = useConfig();

  const [isLoading, setIsLoading] = useState(DEFAULT_CONFIG.isLoading);

  const [modelInfo, setModelInfoState] = useLocalStorage<ModelInfo | undefined>(
    "modelInfo",
    DEFAULT_CONFIG.modelInfo,
    {
      filter: (value) => (value ? { ...value, url: "" } : value),
    },
  );

  const setModelInfo = (info: ModelInfo | undefined) => {
    if (!info?.url) {
      setModelInfoState(undefined);
      return;
    }

    const finalScale = Number(info.kScale || 0.5);
    console.log("Setting model info:", info.type || 'live2d', "scale:", finalScale);

    setModelInfoState({
      ...info,
      type: info.type || 'live2d', // Default to live2d
      kScale: finalScale,
      pointerInteractive:
        "pointerInteractive" in info
          ? info.pointerInteractive
          : (modelInfo?.pointerInteractive ?? true),
      scrollToResize:
        "scrollToResize" in info
          ? info.scrollToResize
          : (modelInfo?.scrollToResize ?? true),
    });
  };

  const contextValue = useMemo(
    () => ({
      modelInfo,
      setModelInfo,
      isLoading,
      setIsLoading,
    }),
    [modelInfo, isLoading, setIsLoading],
  );

  return (
    <Live2DConfigContext.Provider value={contextValue}>
      {children}
    </Live2DConfigContext.Provider>
  );
}

/**
 * Custom hook to use the Live2D configuration context
 * @throws {Error} If used outside of Live2DConfigProvider
 */
export function useLive2DConfig() {
  const context = useContext(Live2DConfigContext);

  if (!context) {
    throw new Error('useLive2DConfig must be used within a Live2DConfigProvider');
  }

  return context;
}

// Export the provider as default
export default Live2DConfigProvider;
