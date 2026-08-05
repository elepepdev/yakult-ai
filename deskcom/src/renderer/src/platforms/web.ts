import type { PlatformAPI, DirectoryResult, FileResult, ConfigFile } from './index';

export class WebPlatform implements PlatformAPI {
  readonly name = 'web';

  // ── Window management (no-op in browser) ──

  setIgnoreMouseEvents(_ignore: boolean): void {}

  toggleForceIgnoreMouse(): void {}

  updateComponentHover(_componentId: string, _isHovering: boolean): void {}

  showContextMenu(): void {}

  hidePet(): void {}

  // ── System event listeners (no-op in browser) ──

  onMicToggle(_callback: () => void): () => void { return () => {}; }
  onInterrupt(_callback: () => void): () => void { return () => {}; }
  onToggleInputSubtitle(_callback: () => void): () => void { return () => {}; }
  onToggleScrollToResize(_callback: () => void): () => void { return () => {}; }
  onSwitchCharacter(_callback: (filename: string) => void): () => void { return () => {}; }
  onToggleForceIgnoreMouse(_callback: () => void): () => void { return () => {}; }
  onForceIgnoreMouseChanged(_callback: (forced: boolean) => void): () => void { return () => {}; }
  onCursorScreenPosition(_callback: (x: number, y: number) => void): () => void { return () => {}; }
  onRestartApp(_callback: () => void): () => void { return () => {}; }

  // ── File system ──

  async getHomeDir(): Promise<string> {
    return '/home/user';
  }

  async listDirectory(_dirPath: string): Promise<DirectoryResult> {
    return { success: false, entries: [], error: 'Not available in browser' };
  }

  async readFile(_filePath: string): Promise<FileResult> {
    return { success: false, error: 'Not available in browser' };
  }

  // ── Config ──

  updateConfigFiles(_files: ConfigFile[]): void {}

  // ── Screen capture ──
  // In web, getDisplayMedia works directly via navigator.mediaDevices

  async getScreenCaptureSource(): Promise<string> {
    return '';
  }
}
