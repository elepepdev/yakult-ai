import {
  BrowserWindow, screen, shell, ipcMain,
} from 'electron';
import { join } from 'path';
import { is } from '@electron-toolkit/utils';

const isMac = process.platform === 'darwin';

export class WindowManager {
  private window: BrowserWindow | null = null;

  private hoveringComponents: Set<string> = new Set();

  private forceIgnoreMouse = false;

  private cursorTrackTimer: NodeJS.Timeout | null = null;

  constructor() {
    ipcMain.on('toggle-force-ignore-mouse', () => {
      this.toggleForceIgnoreMouse();
    });
  }

  createWindow(options: Electron.BrowserWindowConstructorOptions): BrowserWindow {
    this.window = new BrowserWindow({
      width: 900,
      height: 670,
      show: false,
      transparent: true,
      backgroundColor: '#00000000',
      autoHideMenuBar: true,
      frame: false,
      icon: process.platform === 'win32'
        ? join(__dirname, '../../resources/icon.ico')
        : join(__dirname, '../../resources/icon.png'),
      ...(isMac ? { titleBarStyle: 'hiddenInset' } : {}),
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        sandbox: false,
        contextIsolation: true,
        nodeIntegration: false,
      },
      hasShadow: false,
      paintWhenInitiallyHidden: true,
      ...options,
    });

    this.setupWindowEvents();
    this.loadContent();

    this.window.on('enter-full-screen', () => {
      this.window?.webContents.send('window-fullscreen-change', true);
    });

    this.window.on('leave-full-screen', () => {
      this.window?.webContents.send('window-fullscreen-change', false);
    });

    return this.window;
  }

  private setupWindowEvents(): void {
    if (!this.window) return;

    this.window.on('ready-to-show', () => {
      this.window?.show();
      this.window?.webContents.send(
        'window-maximized-change',
        this.window.isMaximized(),
      );
    });

    this.window.on('maximize', () => {
      this.window?.webContents.send('window-maximized-change', true);
    });

    this.window.on('unmaximize', () => {
      this.window?.webContents.send('window-maximized-change', false);
    });

    this.window.on('resize', () => {
      const window = this.getWindow();
      if (window) {
        const bounds = window.getBounds();
        const { width, height } = screen.getPrimaryDisplay().workArea;
        const isMaximized = bounds.width >= width && bounds.height >= height;
        window.webContents.send('window-maximized-change', isMaximized);
      }
    });

    this.window.webContents.setWindowOpenHandler((details) => {
      shell.openExternal(details.url);
      return { action: 'deny' };
    });
  }

  private loadContent(): void {
    if (!this.window) return;

    if (is.dev && process.env.ELECTRON_RENDERER_URL) {
      this.window.loadURL(process.env.ELECTRON_RENDERER_URL);
    } else {
      this.window.loadFile(join(__dirname, '../renderer/index.html'));
    }
  }

  setPetMode(): void {
    if (!this.window) return;

    const displays = screen.getAllDisplays();
    const minX = Math.min(...displays.map((d) => d.bounds.x));
    const minY = Math.min(...displays.map((d) => d.bounds.y));
    const maxX = Math.max(...displays.map((d) => d.bounds.x + d.bounds.width));
    const maxY = Math.max(...displays.map((d) => d.bounds.y + d.bounds.height));
    const combinedWidth = maxX - minX;
    const combinedHeight = maxY - minY;

    this.window.setBounds({
      x: minX,
      y: minY,
      width: combinedWidth,
      height: combinedHeight,
    });

    if (isMac) this.window.setWindowButtonVisibility(false);
    this.window.setResizable(false);
    this.window.setSkipTaskbar(true);
    this.window.setFocusable(false);
    this.window.setAlwaysOnTop(true, 'screen-saver');

    if (isMac) {
      this.window.setIgnoreMouseEvents(true);
      this.window.setVisibleOnAllWorkspaces(true, {
        visibleOnFullScreen: true,
      });
    } else {
      this.window.setIgnoreMouseEvents(true, { forward: true });
    }

    // Prevent the window from being minimized on focus interactions.
    // Some Linux WMs may try to minimize always-on-top frameless windows.
    this.window.on('minimize', (event) => {
      event.preventDefault();
      this.window?.restore();
    });
  }

  getWindow(): BrowserWindow | null {
    return this.window;
  }

  setIgnoreMouseEvents(ignore: boolean): void {
    if (!this.window) return;

    if (isMac) {
      this.window.setIgnoreMouseEvents(ignore);
    } else {
      this.window.setIgnoreMouseEvents(ignore, { forward: true });
    }
  }

  updateComponentHover(componentId: string, isHovering: boolean): void {
    if (isHovering) {
      this.hoveringComponents.add(componentId);
    } else {
      this.hoveringComponents.delete(componentId);
    }

    if (!this.forceIgnoreMouse && this.window) {
      const shouldIgnore = this.hoveringComponents.size === 0;
      if (isMac) {
        this.window.setIgnoreMouseEvents(shouldIgnore);
      } else {
        this.window.setIgnoreMouseEvents(shouldIgnore, { forward: true });
      }
      // Make window focusable when hovering components (allows dragging via WM).
      // Minimize is prevented via 'minimize' event handler in setPetMode().
      this.window.setFocusable(!shouldIgnore);
    }
  }

  toggleForceIgnoreMouse(): void {
    this.forceIgnoreMouse = !this.forceIgnoreMouse;

    if (this.forceIgnoreMouse) {
      if (isMac) {
        this.window?.setIgnoreMouseEvents(true);
      } else {
        this.window?.setIgnoreMouseEvents(true, { forward: true });
      }
      // While passthrough is on, the window no longer receives pointer events, so
      // push the global cursor position to the renderer to keep head-follow working.
      this.startCursorTracking();
    } else {
      const shouldIgnore = this.hoveringComponents.size === 0;
      if (isMac) {
        this.window?.setIgnoreMouseEvents(shouldIgnore);
      } else {
        this.window?.setIgnoreMouseEvents(shouldIgnore, { forward: true });
      }
      this.stopCursorTracking();
    }

    this.window?.webContents.send('force-ignore-mouse-changed', this.forceIgnoreMouse);
  }

  isForceIgnoreMouse(): boolean {
    return this.forceIgnoreMouse;
  }

  private startCursorTracking(): void {
    if (this.cursorTrackTimer) return;
    this.cursorTrackTimer = setInterval(() => {
      const window = this.window;
      if (!window || window.isDestroyed()) return;
      const point = screen.getCursorScreenPoint();
      window.webContents.send('cursor-screen-position', point.x, point.y);
    }, 16); // ~60fps
  }

  private stopCursorTracking(): void {
    if (this.cursorTrackTimer) {
      clearInterval(this.cursorTrackTimer);
      this.cursorTrackTimer = null;
    }
  }
}
