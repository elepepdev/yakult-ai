export interface DirectoryEntry {
  name: string;
  path: string;
  isDir: boolean;
}

export interface DirectoryResult {
  success: boolean;
  entries: DirectoryEntry[];
  error?: string;
}

export interface FileResult {
  success: boolean;
  content?: string;
  error?: string;
}

export interface ConfigFile {
  filename: string;
  name: string;
}

export interface PlatformAPI {
  readonly name: 'electron' | 'web';

  // ── Window management ──
  setIgnoreMouseEvents(ignore: boolean): void;
  toggleForceIgnoreMouse(): void;
  updateComponentHover(componentId: string, isHovering: boolean): void;
  showContextMenu(): void;
  hidePet(): void;

  // ── System event listeners (returns unsubscribe function) ──
  onMicToggle(callback: () => void): () => void;
  onInterrupt(callback: () => void): () => void;
  onToggleInputSubtitle(callback: () => void): () => void;
  onToggleScrollToResize(callback: () => void): () => void;
  onSwitchCharacter(callback: (filename: string) => void): () => void;
  onToggleForceIgnoreMouse(callback: () => void): () => void;
  onForceIgnoreMouseChanged(callback: (forced: boolean) => void): () => void;
  onCursorScreenPosition(callback: (x: number, y: number) => void): () => void;
  onRestartApp(callback: () => void): () => void;

  // ── File system ──
  getHomeDir(): Promise<string>;
  listDirectory(dirPath: string): Promise<DirectoryResult>;
  readFile(filePath: string): Promise<FileResult>;

  // ── Config ──
  updateConfigFiles(files: ConfigFile[]): void;

  // ── Screen capture ──
  getScreenCaptureSource(): Promise<string>;
}

let platform: PlatformAPI | null = null;

export async function initPlatform(): Promise<PlatformAPI> {
  if (platform) return platform;
  try {
    if (typeof window !== 'undefined' && (window as any).api !== undefined) {
      const { ElectronPlatform } = await import('./electron');
      platform = new ElectronPlatform();
    } else {
      const { WebPlatform } = await import('./web');
      platform = new WebPlatform();
    }
  } catch (e) {
    console.warn('Platform detection failed, falling back to web:', e);
    const { WebPlatform } = await import('./web');
    platform = new WebPlatform();
  }
  return platform;
}

export function getPlatform(): PlatformAPI {
  if (!platform) throw new Error('Platform not initialized. Call initPlatform() first.');
  return platform;
}
