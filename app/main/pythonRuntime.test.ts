import { describe, expect, it } from "vitest";
import { resolvePythonRuntime } from "./pythonRuntime";

const paths = {
  packagedPython: "C:/package/python/python.exe",
  developmentPrivatePython: "C:/repo/desktop/runtime/python/python.exe",
  virtualEnvPython: "C:/repo/.venv/Scripts/python.exe"
};

describe("Python runtime resolution", () => {
  it("fails closed in packaged mode without consulting development or system Python", () => {
    const resolution = resolvePythonRuntime({
      ...paths,
      isPackaged: true,
      allowSystemPython: true,
      pathExists: (path) => path === paths.virtualEnvPython
    });

    expect(resolution.executable).toBeNull();
    expect(resolution.source).toBe("missing");
    expect(resolution.error).toMatch(/Startup is blocked/);
  });

  it("prefers the private development runtime and then the project virtual environment", () => {
    const privateRuntime = resolvePythonRuntime({
      ...paths,
      isPackaged: false,
      allowSystemPython: false,
      pathExists: (path) => path === paths.developmentPrivatePython || path === paths.virtualEnvPython
    });
    const virtualEnvironment = resolvePythonRuntime({
      ...paths,
      isPackaged: false,
      allowSystemPython: false,
      pathExists: (path) => path === paths.virtualEnvPython
    });

    expect(privateRuntime.source).toBe("development-private");
    expect(virtualEnvironment.source).toBe("development-venv");
  });

  it("permits a system Python command only after an explicit development opt-in", () => {
    const blocked = resolvePythonRuntime({
      ...paths,
      isPackaged: false,
      allowSystemPython: false,
      pathExists: () => false
    });
    const allowed = resolvePythonRuntime({
      ...paths,
      isPackaged: false,
      allowSystemPython: true,
      systemPythonCommand: "py",
      pathExists: () => false
    });

    expect(blocked.executable).toBeNull();
    expect(allowed).toMatchObject({
      executable: "py",
      source: "development-system",
      error: null
    });
  });
});
