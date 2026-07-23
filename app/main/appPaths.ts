import { app } from "electron";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

export interface AppPaths {
  appDataRoot: string;
  logsRoot: string;
  runtimeRoot: string;
  resourceRoot: string;
  backendRoot: string;
  pythonExecutable: string;
}

export function resolveAppPaths(): AppPaths {
  const localAppData = process.env.LOCALAPPDATA || app.getPath("userData");
  const appDataRoot = join(localAppData, "NEWXAU");
  const developmentRoot = resolve(app.getAppPath());
  const backendRoot = app.isPackaged ? join(process.resourcesPath, "backend") : developmentRoot;
  const packagedPython = join(process.resourcesPath, "python", "python.exe");
  const virtualEnvPython = join(developmentRoot, ".venv", "Scripts", "python.exe");
  const pythonExecutable = existsSync(packagedPython)
    ? packagedPython
    : existsSync(virtualEnvPython)
      ? virtualEnvPython
      : "python";

  return {
    appDataRoot,
    logsRoot: join(appDataRoot, "logs"),
    runtimeRoot: join(appDataRoot, "runtime"),
    resourceRoot: backendRoot,
    backendRoot,
    pythonExecutable
  };
}
