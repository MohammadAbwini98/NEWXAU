import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const python = resolve("desktop", "runtime", "python", "python.exe");
if (!existsSync(python)) {
  console.error(
    "Private desktop Python runtime is not staged at desktop/runtime/python/python.exe. " +
    "See docs/desktop/PACKAGING.md."
  );
  process.exit(1);
}

const smoke = spawnSync(
  python,
  [
    "-c",
    [
      "import fastapi, uvicorn, numpy, pandas, sklearn",
      "import torch, lightgbm, onnxruntime, psycopg",
      "import gold_signal_system.api",
      "print('NEWXAU_PRIVATE_RUNTIME_OK')"
    ].join("; ")
  ],
  {
    cwd: resolve("."),
    encoding: "utf8",
    env: {
      ...process.env,
      PYTHONPATH: resolve("src"),
      ENABLE_BACKGROUND_CYCLE_RUNNER: "0",
      ENABLE_LIVE_PRICE_STREAM: "0",
      CAPITAL_EXECUTION_ENABLED: "0",
      CAPITAL_EXECUTION_AUTO_EXECUTE: "0",
      CAPITAL_EXECUTION_DEMO_ONLY: "1"
    }
  }
);

if (smoke.status !== 0 || !smoke.stdout.includes("NEWXAU_PRIVATE_RUNTIME_OK")) {
  process.stderr.write(smoke.stderr || smoke.stdout || "Private runtime import smoke failed.\n");
  process.exit(smoke.status || 1);
}

console.log("Private desktop Python runtime import smoke passed.");
