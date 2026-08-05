import { useProactiveSpeak } from '@/context/proactive-speak-context';

export function useAgentSettings() {
  const { settings, updateSettings } = useProactiveSpeak();

  const setAllowProactiveSpeak = (val: boolean) => {
    updateSettings({ ...settings, allowProactiveSpeak: val });
  };

  const setIdleSecondsToSpeak = (val: number) => {
    updateSettings({ ...settings, idleSecondsToSpeak: val });
  };

  const setAllowButtonTrigger = (val: boolean) => {
    updateSettings({ ...settings, allowButtonTrigger: val });
  };

  return {
    allowProactiveSpeak: settings.allowProactiveSpeak,
    setAllowProactiveSpeak,
    idleSecondsToSpeak: settings.idleSecondsToSpeak,
    setIdleSecondsToSpeak,
    allowButtonTrigger: settings.allowButtonTrigger,
    setAllowButtonTrigger,
  };
}
