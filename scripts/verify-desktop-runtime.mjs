import { createHash } from "node:crypto";
import {
  cpSync,
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync
} from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";

const root = resolve(".");
const runtimeRoot = resolve(root, "desktop", "runtime", "python");
const python = resolve(runtimeRoot, "python.exe");
const policyPath = resolve(root, "desktop", "runtime-policy.json");
const runtimeManifestPath = resolve(runtimeRoot, "runtime-manifest.json");
const runtimeHashPath = resolve(runtimeRoot, "runtime-manifest.sha256");
const modelsRoot = resolve(root, "models");
const modelManifestPath = resolve(root, "desktop", "runtime", "model-manifest.json");
const modelHashPath = resolve(root, "desktop", "runtime", "model-manifest.sha256");
const ignoredModelParts = new Set([".cache", "__pycache__", "_artifacts_5m_backup"]);

function fail(message) {
  console.error(message);
  process.exit(1);
}

function sha256Text(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function toPosix(path) {
  return path.split(sep).join("/");
}

function listFiles(directory, shouldInclude = () => true) {
  const files = [];
  const visit = (current) => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const fullPath = resolve(current, entry.name);
      if (entry.isDirectory()) visit(fullPath);
      else if (entry.isFile() && shouldInclude(fullPath)) files.push(fullPath);
    }
  };
  visit(directory);
  return files.sort((left, right) => left.localeCompare(right));
}

function readJson(path, label) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`${label} is missing or invalid: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function verifyManifestHash(manifestPath, sidecarPath, label) {
  if (!existsSync(sidecarPath)) fail(`${label} hash sidecar is missing.`);
  const expected = readFileSync(sidecarPath, "utf8").trim().split(/\s+/)[0]?.toLowerCase();
  const actual = sha256Text(readFileSync(manifestPath, "utf8"));
  if (!expected || expected !== actual) fail(`${label} hash does not match its SHA-256 sidecar.`);
}

function verifyInventory(rootPath, manifestFiles, actualPaths, label) {
  const expected = new Map(manifestFiles.map((item) => [item.path, item]));
  const actual = new Set(actualPaths.map((path) => toPosix(relative(rootPath, path))));
  for (const relativePath of actual) {
    if (!expected.has(relativePath)) fail(`${label} contains unexpected file: ${relativePath}`);
  }
  for (const [relativePath, item] of expected) {
    const path = resolve(rootPath, relativePath);
    if (!actual.has(relativePath) || !existsSync(path)) fail(`${label} file is missing: ${relativePath}`);
    if (statSync(path).size !== item.bytes) fail(`${label} size mismatch: ${relativePath}`);
    if (sha256File(path) !== item.sha256) fail(`${label} SHA-256 mismatch: ${relativePath}`);
  }
}

for (const required of [
  python,
  policyPath,
  runtimeManifestPath,
  runtimeHashPath,
  modelManifestPath,
  modelHashPath
]) {
  if (!existsSync(required)) {
    fail(
      "Private desktop release inputs are incomplete. Stage the runtime and run " +
      "`npm run runtime:manifests` before packaging."
    );
  }
}

const policy = readJson(policyPath, "Runtime policy");
const runtimeManifest = readJson(runtimeManifestPath, "Runtime manifest");
const modelManifest = readJson(modelManifestPath, "Model manifest");
verifyManifestHash(runtimeManifestPath, runtimeHashPath, "Runtime manifest");
verifyManifestHash(modelManifestPath, modelHashPath, "Model manifest");

const runtimeFiles = listFiles(
  runtimeRoot,
  (path) => path !== runtimeManifestPath && path !== runtimeHashPath
);
verifyInventory(runtimeRoot, runtimeManifest.files, runtimeFiles, "Private runtime");

for (const required of policy.requiredRuntimeFiles) {
  if (!existsSync(resolve(runtimeRoot, required))) fail(`Required runtime file is missing: ${required}`);
}
for (const item of runtimeManifest.files) {
  if (policy.forbiddenRuntimeExtensions.includes(extname(item.path).toLowerCase())) {
    fail(`Forbidden script type is present in the private runtime: ${item.path}`);
  }
}

const modelFiles = listFiles(modelsRoot, (path) => {
  const parts = toPosix(relative(modelsRoot, path)).split("/");
  return !parts.some((part) => ignoredModelParts.has(part)) && !path.endsWith(".pyc");
});
verifyInventory(modelsRoot, modelManifest.files, modelFiles, "Model bundle");
if (!modelManifest.files.some((item) => [".joblib", ".pt", ".pth", ".onnx", ".safetensors"].includes(extname(item.path).toLowerCase()))) {
  fail("Model manifest contains no binary model artifact.");
}

const verificationRoot = mkdtempSync(join(tmpdir(), "newxau-runtime-verify-"));
const resolvedTempRoot = `${resolve(tmpdir()).toLowerCase()}${sep}`;
if (!resolve(verificationRoot).toLowerCase().startsWith(resolvedTempRoot)) {
  fail("Unsafe temporary verification path.");
}

try {
  const packagedBackend = resolve(verificationRoot, "backend");
  cpSync(resolve(root, "src"), resolve(packagedBackend, "src"), { recursive: true });
  cpSync(resolve(root, "scripts"), resolve(packagedBackend, "scripts"), { recursive: true });
  cpSync(resolve(root, "db"), resolve(packagedBackend, "db"), { recursive: true });

  const smokeScript = [
    "import importlib.metadata as metadata, json, os, platform, sys",
    "sys.path.insert(0, sys.argv[2])",
    "import numpy as np",
    "import torch",
    "import lightgbm as lgb",
    "import onnxruntime as ort",
    "import onnxruntime.capi.onnxruntime_pybind11_state as ort_native",
    "import psycopg, psycopg.pq, psycopg_binary.pq as psycopg_native",
    "from onnxruntime.datasets import get_example",
    "expected = json.loads(sys.argv[1])",
    "actual = {name: metadata.version(name) for name in expected['packages']}",
    "assert platform.python_version() == expected['python']['version']",
    "assert platform.architecture()[0] == expected['python']['architecture']",
    "assert platform.machine().upper() == expected['python']['machine'].upper()",
    "assert actual == expected['packages']",
    "assert os.environ['CAPITAL_EXECUTION_ENABLED'] == '0'",
    "assert os.environ['CAPITAL_EXECUTION_AUTO_EXECUTE'] == '0'",
    "assert os.environ['CAPITAL_EXECUTION_DEMO_ONLY'] == '1'",
    "assert os.environ['DATA_PROVIDER'] == 'synthetic'",
    "assert abs(float(torch.softmax(torch.tensor([[1.0, 2.0, 3.0]]), dim=1).sum()) - 1.0) < 1e-6",
    "X = np.array([[0.0], [1.0], [2.0], [3.0]], dtype=np.float32)",
    "y = np.array([0, 0, 1, 1])",
    "model = lgb.LGBMClassifier(n_estimators=2, min_child_samples=1, verbosity=-1).fit(X, y)",
    "assert len(model.predict(X)) == 4",
    "session = ort.InferenceSession(get_example('mul_1.onnx'), providers=['CPUExecutionProvider'])",
    "input_meta = session.get_inputs()[0]",
    "assert session.run(None, {input_meta.name: np.ones((3, 2), dtype=np.float32)})",
    "assert psycopg.pq.version() > 0",
    "import gold_signal_system.api",
    "runtime = gold_signal_system.api.runtime",
    "assert runtime.capital_execution_enabled is False",
    "assert runtime.capital_execution_auto_execute is False",
    "assert runtime.capital_execution_demo_only is True",
    "native = {'torch': torch._C.__file__, 'lightgbm': lgb.basic._LIB._name, 'onnxruntime': ort_native.__file__, 'psycopg': psycopg_native.__file__}",
    "assert all(path and os.path.exists(path) for path in native.values())",
    "print(json.dumps({'event': 'NEWXAU_PRIVATE_RUNTIME_OK', 'native': native, 'packages': actual}))"
  ].join("; ");

  const smoke = spawnSync(
    python,
    ["-c", smokeScript, JSON.stringify(policy), resolve(packagedBackend, "src")],
    {
    cwd: packagedBackend,
    encoding: "utf8",
    env: {
      SYSTEMROOT: process.env.SYSTEMROOT ?? "",
      WINDIR: process.env.WINDIR ?? "",
      TEMP: process.env.TEMP ?? "",
      TMP: process.env.TMP ?? "",
      PATH: runtimeRoot,
      PYTHONPATH: resolve(packagedBackend, "src"),
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONUNBUFFERED: "1",
      DATA_PROVIDER: "synthetic",
      ENABLE_BACKGROUND_CYCLE_RUNNER: "0",
      ENABLE_LIVE_PRICE_STREAM: "0",
      CAPITAL_EXECUTION_ENABLED: "0",
      CAPITAL_EXECUTION_AUTO_EXECUTE: "0",
      CAPITAL_EXECUTION_DEMO_ONLY: "1",
      NEWXAU_RUNTIME_ROOT: resolve(verificationRoot, "runtime-state"),
      NEWXAU_RESOURCE_ROOT: packagedBackend
    }
    }
  );

  if (smoke.status !== 0 || !smoke.stdout.includes("NEWXAU_PRIVATE_RUNTIME_OK")) {
    fail(smoke.stderr || smoke.stdout || "Private runtime native inference smoke failed.");
  }
} finally {
  const candidate = resolve(verificationRoot);
  if (candidate.startsWith(resolve(tmpdir()))) rmSync(candidate, { recursive: true, force: true });
}

console.log("Private desktop runtime, model manifests, native inference, and safety checks passed.");
