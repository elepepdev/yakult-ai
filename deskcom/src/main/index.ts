/* eslint-disable no-shadow */
import { app, ipcMain, globalShortcut, desktopCapturer, BrowserWindow } from "electron";
import { electronApp, is, optimizer } from "@electron-toolkit/utils";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import { WindowManager } from "./window-manager";
import { MenuManager } from "./menu-manager";

let windowManager: WindowManager;
let menuManager: MenuManager;
let isQuitting = false;

function setupIPC(): void {
  ipcMain.handle("get-platform", () => process.platform);

  ipcMain.on("set-ignore-mouse-events", (_event, ignore: boolean) => {
    const window = windowManager.getWindow();
    if (window) {
      windowManager.setIgnoreMouseEvents(ignore);
    }
  });

  ipcMain.on("window-minimize", () => {
    windowManager.getWindow()?.minimize();
  });

  ipcMain.on("window-maximize", () => {
    const window = windowManager.getWindow();
    if (window) {
      windowManager.maximizeWindow();
    }
  });

  ipcMain.on("window-close", () => {
    const window = windowManager.getWindow();
    if (window) {
      if (process.platform === "darwin") {
        window.hide();
      } else {
        window.close();
      }
    }
  });

  ipcMain.on("hide-pet", () => {
    const window = windowManager.getWindow();
    if (window) {
      window.hide();
    }
  });

  ipcMain.on(
    "update-component-hover",
    (_event, componentId: string, isHovering: boolean) => {
      windowManager.updateComponentHover(componentId, isHovering);
    },
  );

  ipcMain.handle("get-config-files", () => {
    const configFiles = JSON.parse(localStorage.getItem("configFiles") || "[]");
    menuManager.updateConfigFiles(configFiles);
    return configFiles;
  });

  ipcMain.on("update-config-files", (_event, files) => {
    menuManager.updateConfigFiles(files);
  });

  ipcMain.handle('get-screen-capture', async () => {
    const sources = await desktopCapturer.getSources({ types: ['screen'] });
    return sources[0].id;
  });

  ipcMain.on('restart-app', () => {
    app.relaunch();
    app.exit(0);
  });

  ipcMain.handle("get-home-dir", () => os.homedir());

  ipcMain.on("window-raise", () => {
    const win = windowManager.getWindow();
    if (win) {
      win.setAlwaysOnTop(true, "screen-saver");
      win.focus();
      win.moveTop();
    }
  });

  ipcMain.handle("read-file", async (_event, filePath: string) => {
    try {
      const content = fs.readFileSync(filePath, "utf-8");
      return { success: true, content };
    } catch (err: any) {
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle("resolve-directory", async (_event, inputPath: string) => {
    const homedir = os.homedir();
    let resolved = inputPath.trim();
    if (!resolved) resolved = homedir;
    resolved = resolved.replace(/^~/, homedir);

    let dirPath: string;
    let filterPrefix: string | null = null;

    try {
      const stat = fs.statSync(resolved);
      if (stat.isDirectory()) {
        dirPath = resolved;
      } else {
        dirPath = path.dirname(resolved);
        filterPrefix = path.basename(resolved);
      }
    } catch {
      const parent = path.dirname(resolved);
      filterPrefix = path.basename(resolved);
      if (parent === resolved) {
        return { success: false, error: "Invalid path", entries: [] };
      }
      dirPath = parent;
    }

    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });
      let results = entries
        .filter((entry) => !entry.name.startsWith("."))
        .map((entry) => ({
          name: entry.name,
          path: path.join(dirPath, entry.name),
          isDir: entry.isDirectory(),
        }));

      if (filterPrefix) {
        const lower = filterPrefix.toLowerCase();
        results = results.filter((e) => e.name.toLowerCase().startsWith(lower));
      }

      results.sort((a, b) => {
        if (a.isDir && !b.isDir) return -1;
        if (!a.isDir && b.isDir) return 1;
        return a.name.localeCompare(b.name);
      });

      return { success: true, entries: results };
    } catch (err: any) {
      return { success: false, error: err.message, entries: [] };
    }
  });
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId("com.electron");

  windowManager = new WindowManager();
  menuManager = new MenuManager();

  const window = windowManager.createWindow({
    titleBarOverlay: {
      color: "#111111",
      symbolColor: "#FFFFFF",
      height: 30,
    },
  });
  windowManager.setPetMode();
  menuManager.createTray();

  window.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    const levels = ['verbose', 'info', 'warning', 'error'];
    console.log(`[renderer:${levels[level] || 'unknown'}] ${message} (${sourceId}:${line})`);
  });

  window.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      window.hide();
    }
    return false;
  });

  // F8 to toggle passthrough
  globalShortcut.register('F8', () => {
    windowManager.toggleForceIgnoreMouse();
  });

  setupIPC();

  app.on("activate", () => {
    const window = windowManager.getWindow();
    if (window) {
      window.show();
    }
  });

  app.on("browser-window-created", (_, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  app.on('web-contents-created', (_, contents) => {
    contents.session.setPermissionRequestHandler((webContents, permission, callback) => {
      if (permission === 'media') {
        callback(true);
      } else {
        callback(false);
      }
    });
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  menuManager.destroy();
  globalShortcut.unregisterAll();
});
