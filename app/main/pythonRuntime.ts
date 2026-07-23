import { existsSync } from "node:fs";

export type PythonRuntimeSource =
  | "packaged-private"
  | "development-private"
  | "development-venv"
  | "development-system"
  | "missing";

export interface PythonRuntimeResolution {
  executable: string | null;
  source: PythonRuntimeSource;
  error: string | null;
}

export interface PythonRuntimeOptions {
  isPackaged: boolean;
  packagedPython: string;
  developmentPrivatePython: string;
  virtualEnvPython: string;
  allowSystemPython: boolean;
  systemPythonCommand?: string;
  pathExists?: (path: string) => boolean;
}

export function resolvePythonRuntime(options: PythonRuntimeOptions): PythonRuntimeResolution {
  const pathExists = options.pathExists ?? existsSync;

  if (options.isPackaged) {
    if (pathExists(options.packagedPython)) {
      return {
        executable: options.packagedPython,
        source: "packaged-private",
        error: null
      };
    }
    return {
      executable: null,
      source: "missing",
      error:
        "The packaged NEWXAU Python runtime is missing or incomplete. " +
        "Startup is blocked; reinstall a verified NEWXAU package."
    };
  }

  if (pathExists(options.developmentPrivatePython)) {
    return {
      executable: options.developmentPrivatePython,
      source: "development-private",
      error: null
    };
  }
  if (pathExists(options.virtualEnvPython)) {
    return {
      executable: options.virtualEnvPython,
      source: "development-venv",
      error: null
    };
  }
  if (options.allowSystemPython) {
    return {
      executable: options.systemPythonCommand?.trim() || "python",
      source: "development-system",
      error: null
    };
  }
  return {
    executable: null,
    source: "missing",
    error:
      "No private or project virtual-environment Python runtime was found. " +
      "System Python is disabled unless NEWXAU_ALLOW_SYSTEM_PYTHON=1 is explicitly set for development."
  };
}
