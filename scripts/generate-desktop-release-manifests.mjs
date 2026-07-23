import { createHash } from "node:crypto";
import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync
} from "node:fs";
import { extname, relative, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(".");
const runtimeRoot = resolve(root, "desktop", "runtime", "python");
const python = resolve(runtimeRoot, "python.exe");
const modelsRoot = resolve(root, "models");
const runtimeManifestPath = resolve(runtimeRoot, "runtime-manifest.json");
const runtimeHashPath = resolve(runtimeRoot, "runtime-manifest.sha256");
const modelManifestPath = resolve(root, "desktop", "runtime", "model-manifest.json");
const modelHashPath = resolve(root, "desktop", "runtime", "model-manifest.sha256");
const scriptExtensions = new Set([".exe", ".com", ".py", ".pyw", ".bat", ".cmd", ".ps1", ".vbs", ".wsf"]);

function sha256File(path) {
  const hash = createHash("sha256");
  hash.update(readFileSync(path));
  return hash.digest("hex");
}

function toPosix(path) {
  return path.split(sep).join("/");
}

function listFiles(directory, shouldInclude = () => true) {
  const files = [];
  const visit = (current) => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const fullPath = resolve(current, entry.name);
      if (entry.isDirectory()) {
        visit(fullPath);
      } else if (entry.isFile() && shouldInclude(fullPath)) {
        files.push(fullPath);
      }
    }
  };
  visit(directory);
  return files.sort((left, right) => left.localeCompare(right));
}

function writeManifest(path, hashPath, payload) {
  const text = `${JSON.stringify(payload, null, 2)}\n`;
  writeFileSync(path, text, "utf8");
  writeFileSync(hashPath, `${createHash("sha256").update(text).digest("hex")}  ${relative(root, path)}\n`, "utf8");
}

if (!existsSync(python)) {
  throw new Error("Stage the private runtime before generating release manifests.");
}

const metadataScript = [
  "import importlib.metadata as metadata, json, platform, sys",
  "packages = json.loads(sys.argv[1])",
  "print(json.dumps({'version': platform.python_version(), 'architecture': platform.architecture()[0], 'machine': platform.machine(), 'packages': {name: metadata.version(name) for name in packages}}))"
].join("; ");
const packageNames = Object.keys(JSON.parse(readFileSync(resolve(root, "desktop", "runtime-policy.json"), "utf8")).packages);
const metadata = spawnSync(python, ["-c", metadataScript, JSON.stringify(packageNames)], {
  cwd: runtimeRoot,
  encoding: "utf8",
  env: {
    SYSTEMROOT: process.env.SYSTEMROOT ?? "",
    WINDIR: process.env.WINDIR ?? "",
    TEMP: process.env.TEMP ?? "",
    TMP: process.env.TMP ?? "",
    PATH: runtimeRoot
  }
});
if (metadata.status !== 0) {
  throw new Error(metadata.stderr || metadata.stdout || "Private runtime metadata collection failed.");
}

const runtimeFiles = listFiles(
  runtimeRoot,
  (path) => path !== runtimeManifestPath && path !== runtimeHashPath
).map((path) => {
  const relativePath = toPosix(relative(runtimeRoot, path));
  return {
    path: relativePath,
    bytes: statSync(path).size,
    sha256: sha256File(path),
    executableOrScript: scriptExtensions.has(extname(path).toLowerCase())
  };
});
writeManifest(runtimeManifestPath, runtimeHashPath, {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  runtime: JSON.parse(metadata.stdout.trim()),
  files: runtimeFiles
});

const ignoredModelParts = new Set([".cache", "__pycache__", "_artifacts_5m_backup"]);
const modelFiles = listFiles(modelsRoot, (path) => {
  const parts = toPosix(relative(modelsRoot, path)).split("/");
  return !parts.some((part) => ignoredModelParts.has(part)) && !path.endsWith(".pyc");
}).map((path) => ({
  path: toPosix(relative(modelsRoot, path)),
  bytes: statSync(path).size,
  sha256: sha256File(path)
}));
writeManifest(modelManifestPath, modelHashPath, {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  files: modelFiles
});

console.log(`Generated runtime manifest for ${runtimeFiles.length} files.`);
console.log(`Generated model manifest for ${modelFiles.length} files.`);
