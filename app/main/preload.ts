import { contextBridge, ipcRenderer } from "electron";
import { IPC, type BackendState, type DesktopBridge, type DesktopRequestInit } from "../shared/contracts";

const bridge: DesktopBridge = {
  window: {
    minimize: () => ipcRenderer.invoke(IPC.windowMinimize),
    toggleMaximize: () => ipcRenderer.invoke(IPC.windowToggleMaximize),
    close: () => ipcRenderer.invoke(IPC.windowClose),
    isMaximized: () => ipcRenderer.invoke(IPC.windowIsMaximized),
    onMaximizedChange: (callback) => {
      const listener = (_event: Electron.IpcRendererEvent, maximized: boolean) => callback(maximized);
      ipcRenderer.on(IPC.windowMaximizedChanged, listener);
      return () => ipcRenderer.removeListener(IPC.windowMaximizedChanged, listener);
    }
  },
  backend: {
    getState: () => ipcRenderer.invoke(IPC.backendGetState),
    restart: () => ipcRenderer.invoke(IPC.backendRestart),
    onStateChange: (callback) => {
      const listener = (_event: Electron.IpcRendererEvent, state: BackendState) => callback(state);
      ipcRenderer.on(IPC.backendStateChanged, listener);
      return () => ipcRenderer.removeListener(IPC.backendStateChanged, listener);
    },
    request: (path: string, init?: DesktopRequestInit) => ipcRenderer.invoke(IPC.backendRequest, path, init),
    websocketConfig: () => ipcRenderer.invoke(IPC.backendWebsocketConfig)
  },
  settings: {
    get: () => ipcRenderer.invoke(IPC.settingsGet),
    update: (patch) => ipcRenderer.invoke(IPC.settingsUpdate, patch)
  },
  secrets: {
    status: () => ipcRenderer.invoke(IPC.secretsStatus),
    set: (name, value) => ipcRenderer.invoke(IPC.secretsSet, name, value),
    remove: (name) => ipcRenderer.invoke(IPC.secretsRemove, name)
  },
  platform: process.platform
};

contextBridge.exposeInMainWorld("newxau", bridge);
