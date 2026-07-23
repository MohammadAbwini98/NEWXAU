import { app } from "electron";
import { join, resolve } from "node:path";
import { resolvePythonRuntime, type PythonRuntimeSource } from "./pythonRuntime";

export interface AppPaths {
  appDataRoot: string;
  logsRoot: string;
  runtimeRoot: string;
  resourceRoot: string;
  backendRoot: string;
  pythonExecutable: string | null;
  pythonRuntimeSource: PythonRuntimeSource;
  pythonResolutionError: string | null;
}

export function resolveAppPaths(): AppPaths {
  const localAppData = process.env.LOCALAPPDATA || app.getPath("userData");
  const appDataRoot = process.env.NEWXAU_DESKTOP_USER_DATA_ROOT
    ? resolve(process.env.NEWXAU_DESKTOP_USER_DATA_ROOT)
    : join(localAppData, "NEWXAU");
  const developmentRoot = resolve(app.getAppPath());
  const backendRoot = app.isPackaged ? join(process.resourcesPath, "backend") : developmentRoot;
  const packagedPython = join(process.resourcesPath, "python", "python.exe");
  const developmentPrivatePython = join(developmentRoot, "desktop", "runtime", "python", "python.exe");
  const virtualEnvPython = join(developmentRoot, ".venv", "Scripts", "python.exe");
  const pythonRuntime = resolvePythonRuntime({
    isPackaged: app.isPackaged,
    packagedPython,
    developmentPrivatePython,
    virtualEnvPython,
    allowSystemPython: !app.isPackaged && process.env.NEWXAU_ALLOW_SYSTEM_PYTHON === "1",
    systemPythonCommand: process.env.NEWXAU_SYSTEM_PYTHON_COMMAND
  });

  return {
    appDataRoot,
    logsRoot: join(appDataRoot, "logs"),
    runtimeRoot: join(appDataRoot, "runtime"),
    resourceRoot: backendRoot,
    backendRoot,
    pythonExecutable: pythonRuntime.executable,
    pythonRuntimeSource: pythonRuntime.source,
    pythonResolutionError: pythonRuntime.error
  };
}
