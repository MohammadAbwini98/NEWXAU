import { app, BrowserWindow, ipcMain, shell } from "electron";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { dirname } from "node:path";
import { BackendProcessManager } from "./backendProcessManager";
import { resolveAppPaths } from "./appPaths";
import { SettingsStore } from "./settingsStore";
import { SecretStore } from "./secretStore";
import { assertTrustedSender } from "./senderGuard";
import { IPC, type DesktopRequestInit, type DesktopSettings } from "../shared/contracts";

let mainWindow: BrowserWindow | null = null;
const gotSingleInstanceLock = app.requestSingleInstanceLock();
const headlessSmoke = process.env.NEWXAU_DESKTOP_HEADLESS_SMOKE === "1";
const legacyCaptureUrl = process.env.NEWXAU_LEGACY_CAPTURE_URL;
const smokeRoute = process.env.NEWXAU_DESKTOP_SMOKE_ROUTE;

if (legacyCaptureUrl && !/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(legacyCaptureUrl)) {
  throw new Error("NEWXAU_LEGACY_CAPTURE_URL must be a loopback dashboard URL.");
}
if (smokeRoute && !/^[a-z][a-z-]{0,40}$/.test(smokeRoute)) {
  throw new Error("NEWXAU_DESKTOP_SMOKE_ROUTE is invalid.");
}

if (!gotSingleInstanceLock) {
  app.quit();
} else {
  const paths = resolveAppPaths();
  const settings = new SettingsStore(paths.appDataRoot);
  const secrets = new SecretStore(paths.appDataRoot);
  const backend = new BackendProcessManager(paths, secrets);

  function trusted<T extends unknown[], R>(
    handler: (event: Electron.IpcMainInvokeEvent, ...args: T) => R | Promise<R>
  ) {
    return (event: Electron.IpcMainInvokeEvent, ...args: T) => {
      assertTrustedSender(event);
      return handler(event, ...args);
    };
  }

  function registerIpc(): void {
    ipcMain.handle(IPC.windowMinimize, trusted(() => mainWindow?.minimize()));
    ipcMain.handle(IPC.windowToggleMaximize, trusted(() => {
      if (!mainWindow) return;
      if (mainWindow.isMaximized()) mainWindow.unmaximize();
      else mainWindow.maximize();
    }));
    ipcMain.handle(IPC.windowClose, trusted(() => mainWindow?.close()));
    ipcMain.handle(IPC.windowIsMaximized, trusted(() => mainWindow?.isMaximized() ?? false));
    ipcMain.handle(IPC.backendGetState, trusted(() => backend.getState()));
    ipcMain.handle(IPC.backendRestart, trusted(() => backend.restart()));
    ipcMain.handle(IPC.backendRequest, trusted((_event, path: string, init?: DesktopRequestInit) => backend.request(path, init)));
    ipcMain.handle(IPC.backendWebsocketConfig, trusted(() => backend.getWebsocketConfig()));
    ipcMain.handle(IPC.settingsGet, trusted(() => settings.get()));
    ipcMain.handle(IPC.settingsUpdate, trusted((_event, patch: Partial<DesktopSettings>) => settings.update(patch)));
    ipcMain.handle(IPC.secretsStatus, trusted(() => secrets.status()));
    ipcMain.handle(IPC.secretsSet, trusted((_event, name: string, value: string) => secrets.set(name, value)));
    ipcMain.handle(IPC.secretsRemove, trusted((_event, name: string) => secrets.remove(name)));
    backend.on("state", (state) => mainWindow?.webContents.send(IPC.backendStateChanged, state));
  }

  async function createWindow(): Promise<void> {
    mainWindow = new BrowserWindow({
      width: 1480,
      height: 940,
      minWidth: 1120,
      minHeight: 720,
      frame: false,
      show: false,
      backgroundColor: "#080b10",
      title: "NEWXAU",
      webPreferences: {
        preload: join(__dirname, "../preload/preload.mjs"),
        contextIsolation: true,
        nodeIntegration: false,
        // electron-vite emits an ESM preload. Electron requires ESM preloads to run
        // unsandboxed; privilege remains constrained by context isolation, the narrow
        // contextBridge surface, sender checks, and navigation lockdown.
        sandbox: false,
        webSecurity: true
      }
    });

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith("https://")) void shell.openExternal(url);
      return { action: "deny" };
    });
    mainWindow.webContents.on("will-navigate", (event, url) => {
      const current = mainWindow?.webContents.getURL() ?? "";
      if (url !== current) event.preventDefault();
    });
    mainWindow.webContents.on("preload-error", (_event, preloadPath, error) => {
      console.error(`[preload-error] ${preloadPath}: ${error.message}`);
    });
    if (headlessSmoke) {
      mainWindow.webContents.on("console-message", (_event, level, message, line, sourceId) => {
        console.log(JSON.stringify({ event: "renderer-console", level, message, line, source: sourceId }));
      });
      mainWindow.webContents.on("render-process-gone", (_event, details) => {
        console.error(`[render-process-gone] ${details.reason} (${details.exitCode})`);
      });
    }
    mainWindow.on("maximize", () => mainWindow?.webContents.send(IPC.windowMaximizedChanged, true));
    mainWindow.on("unmaximize", () => mainWindow?.webContents.send(IPC.windowMaximizedChanged, false));
    mainWindow.once("ready-to-show", () => {
      if (!headlessSmoke) mainWindow?.show();
    });
    mainWindow.on("closed", () => {
      mainWindow = null;
    });

    if (legacyCaptureUrl) {
      await mainWindow.loadURL(legacyCaptureUrl);
    } else if (process.env.ELECTRON_RENDERER_URL) {
      await mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
    } else {
      await mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
    }
  }

  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });

  app.whenReady().then(async () => {
    registerIpc();
    if (headlessSmoke && smokeRoute) {
      await settings.update({ lastRouteId: smokeRoute, appearance: "dark" });
    }
    await createWindow();
    const desktopSettings = await settings.get();
    if (!legacyCaptureUrl && (desktopSettings.launchBackendOnStart || headlessSmoke)) await backend.start();
    if (headlessSmoke) {
      if (!legacyCaptureUrl) {
        const deadline = Date.now() + 20_000;
        while (backend.getState().phase !== "ready" && Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
      }
      const state = backend.getState();
      const capturePath = process.env.NEWXAU_DESKTOP_CAPTURE_PATH;
      if (capturePath && mainWindow) {
        await new Promise((resolve) => setTimeout(resolve, 2500));
        await mkdir(dirname(capturePath), { recursive: true });
        const image = await mainWindow.webContents.capturePage();
        await writeFile(capturePath, image.toPNG());
      } else if (!legacyCaptureUrl) {
        // Let the renderer finish its first authenticated REST/WebSocket round
        // before the smoke harness begins graceful shutdown.
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      console.log(JSON.stringify({
        event: "desktop-smoke",
        renderer_loaded: Boolean(mainWindow && !mainWindow.webContents.isLoading()),
        backend_phase: state.phase,
        backend_pid: state.pid,
        capture_path: capturePath ?? null
      }));
      if (!legacyCaptureUrl) await backend.stop();
      app.removeAllListeners("before-quit");
      app.quit();
    }
  });

  app.on("before-quit", (event) => {
    if (backend.getState().phase === "stopped") return;
    event.preventDefault();
    void backend.stop().finally(() => {
      app.removeAllListeners("before-quit");
      app.quit();
    });
  });

  app.on("window-all-closed", () => app.quit());
}
