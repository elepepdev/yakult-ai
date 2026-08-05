import { ElectronAPI } from '@electron-toolkit/preload';

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      setIgnoreMouseEvents: (ignore: boolean) => void
      toggleForceIgnoreMouse: () => void
      onForceIgnoreMouseChanged: (callback: (isForced: boolean) => void) => void
      onCursorScreenPosition: (callback: (x: number, y: number) => void) => void
      showContextMenu: (x: number, y: number) => void
      onMicToggle: (callback: () => void) => void
      onInterrupt: (callback: () => void) => void
      updateComponentHover: (componentId: string, isHovering: boolean) => void
      onToggleInputSubtitle: (callback: () => void) => void
      onToggleScrollToResize: (callback: () => void) => void
      onSwitchCharacter: (callback: (filename: string) => void) => void
      getConfigFiles: () => Promise<any>
      updateConfigFiles: (files: any[]) => void
    }
  }
}

interface IpcRenderer {
  send(channel: string, ...args: any[]): void;
}
