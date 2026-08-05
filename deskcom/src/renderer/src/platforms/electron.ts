import type { PlatformAPI, DirectoryResult, FileResult, ConfigFile } from './index';

export class ElectronPlatform implements PlatformAPI {
  readonly name = 'electron';

  get api() { return (window as any).api; }
  get electron() { return (window as any).electron; }

  // ── Window management ──

  setIgnoreMouseEvents(ignore: boolean): void {
    this.api?.setIgnoreMouseEvents(ignore);
  }

  toggleForceIgnoreMouse(): void {
    this.api?.toggleForceIgnoreMouse();
  }

  updateComponentHover(componentId: string, isHovering: boolean): void {
    this.api?.updateComponentHover(componentId, isHovering);
  }

  showContextMenu(): void {
    this.api?.showContextMenu?.();
  }

  hidePet(): void {
    this.api?.hidePet?.();
  }

  // ── System event listeners ──
  //
  // IMPORTANT: Use `window.api.*` (preload context) instead of `window.electron.ipcRenderer.*`
  // for listener registration. The contextBridge wraps ipcRenderer methods, and
  // `removeListener` through contextBridge can fail to match function references
  // due to function proxying, causing listeners to accumulate over time.
  // Preload API methods create handler functions in the preload context where
  // removeListener references match correctly.

  onMicToggle(callback: () => void): () => void {
    const cleanup = this.api?.onMicToggle?.(callback);
    return cleanup ?? (() => {});
  }

  onInterrupt(callback: () => void): () => void {
    const cleanup = this.api?.onInterrupt?.(callback);
    return cleanup ?? (() => {});
  }

  onToggleInputSubtitle(callback: () => void): () => void {
    const cleanup = this.api?.onToggleInputSubtitle?.(callback);
    return cleanup ?? (() => {});
  }

  onToggleScrollToResize(callback: () => void): () => void {
    const cleanup = this.api?.onToggleScrollToResize?.(callback);
    return cleanup ?? (() => {});
  }

  onSwitchCharacter(callback: (filename: string) => void): () => void {
    const cleanup = this.api?.onSwitchCharacter?.(callback);
    return cleanup ?? (() => {});
  }

  onToggleForceIgnoreMouse(callback: () => void): () => void {
    const cleanup = this.api?.onToggleForceIgnoreMouse?.(callback);
    return cleanup ?? (() => {});
  }

  onForceIgnoreMouseChanged(callback: (forced: boolean) => void): () => void {
    const cleanup = this.api?.onForceIgnoreMouseChanged?.(callback);
    return cleanup ?? (() => {});
  }

  onCursorScreenPosition(callback: (x: number, y: number) => void): () => void {
    const cleanup = this.api?.onCursorScreenPosition?.(callback);
    return cleanup ?? (() => {});
  }

  onRestartApp(callback: () => void): () => void {
    const cleanup = this.api?.onRestartApp?.(callback);
    return cleanup ?? (() => {});
  }

  // ── File system ──

  async getHomeDir(): Promise<string> {
    return this.api?.getHomeDir() || '';
  }

  async listDirectory(dirPath: string): Promise<DirectoryResult> {
    return this.api?.listDirectory(dirPath) || { success: false, entries: [], error: 'API unavailable' };
  }

  async readFile(filePath: string): Promise<FileResult> {
    return this.api?.readFile(filePath) || { success: false, error: 'API unavailable' };
  }

  // ── Config ──

  updateConfigFiles(files: ConfigFile[]): void {
    this.api?.updateConfigFiles?.(files);
  }

  // ── Screen capture ──

  async getScreenCaptureSource(): Promise<string> {
    try {
      return await this.electron?.ipcRenderer?.invoke('get-screen-capture') || '';
    } catch {
      return '';
    }
  }
}
