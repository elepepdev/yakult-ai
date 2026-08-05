import { useVAD } from '@/context/vad-context';

export function useASRSettings() {
  const {
    autoStopMic, setAutoStopMic,
    autoStartMicOn, setAutoStartMicOn,
    autoStartMicOnConvEnd, setAutoStartMicOnConvEnd,
    settings, updateSettings,
  } = useVAD();

  const setPositiveSpeechThreshold = (val: number) => {
    updateSettings({ ...settings, positiveSpeechThreshold: val });
  };

  const setNegativeSpeechThreshold = (val: number) => {
    updateSettings({ ...settings, negativeSpeechThreshold: val });
  };

  const setRedemptionFrames = (val: number) => {
    updateSettings({ ...settings, redemptionFrames: val });
  };

  return {
    autoStopMic, setAutoStopMic,
    autoStartMicOn, setAutoStartMicOn,
    autoStartMicOnConvEnd, setAutoStartMicOnConvEnd,
    positiveSpeechThreshold: settings.positiveSpeechThreshold,
    setPositiveSpeechThreshold,
    negativeSpeechThreshold: settings.negativeSpeechThreshold,
    setNegativeSpeechThreshold,
    redemptionFrames: settings.redemptionFrames,
    setRedemptionFrames,
  };
}
