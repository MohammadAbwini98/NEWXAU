# Windows packaging and release gate

NEWXAU uses a private-runtime packaging model. Packaged mode never searches
PATH, a machine-wide Python installation, or the development `.venv`.

## Runtime resolution policy

```text
Development:
  desktop/runtime/python/python.exe
  -> .venv/Scripts/python.exe
  -> system Python only with NEWXAU_ALLOW_SYSTEM_PYTHON=1

Packaged:
  resources/python/python.exe
  -> blocking startup failure
```

`NEWXAU_SYSTEM_PYTHON_COMMAND` may select the explicitly permitted development
executable. It is ignored in packaged mode.

## Build the private runtime

Use Node 22.12 or newer and a repository `.venv`:

```powershell
npm ci
npm run runtime:build
npm run runtime:verify
```

`runtime:build` downloads the official CPython 3.12.10 x64 embeddable archive,
checks the PSF-published SHA-256 recorded in `desktop/runtime-policy.json`,
installs `desktop/runtime-requirements.txt` as binary wheels, warms the pinned
imports so controlled bytecode is included in the inventory, and generates:

```text
desktop/runtime/python/runtime-manifest.json
desktop/runtime/python/runtime-manifest.sha256
desktop/runtime/model-manifest.json
desktop/runtime/model-manifest.sha256
```

The generated runtime, manifests, model weights, and packages are release
inputs and are intentionally ignored by Git.

The Electron-owned backend sets `PYTHONDONTWRITEBYTECODE=1`. Runtime execution
must not add files after the manifest is created.

## Verification coverage

`npm run runtime:verify` fails unless all of these pass:

- exact Python version, x64 architecture, and machine type;
- exact approved package versions;
- complete SHA-256 runtime and model inventories with no extra files;
- required CPython DLLs and no forbidden script extensions;
- Torch, LightGBM, and ONNX Runtime minimal inference;
- native PostgreSQL driver loading without a database connection;
- backend import from a temporary packaged-resource layout unrelated to the
  repository working directory;
- execution disabled, auto-execution disabled, demo-only enabled, and synthetic
  provider safety environment;
- presence of a binary model artifact in the model manifest.

## Unsigned test packages

```powershell
npm run package:dir
npm run package:win
```

The unpacked output is `release/win-unpacked`. The unsigned test artifacts are:

```text
release/NEWXAU-0.1.0-x64-installer.exe
release/NEWXAU-0.1.0-x64-portable.exe
```

They remain test-only until signing is configured. Confirm with:

```powershell
Get-AuthenticodeSignature release\win-unpacked\NEWXAU.exe
Get-AuthenticodeSignature release\NEWXAU-0.1.0-x64-installer.exe
Get-AuthenticodeSignature release\NEWXAU-0.1.0-x64-portable.exe
```

For isolated lifecycle smoke, remove any inherited
`ELECTRON_RUN_AS_NODE` value and set a temporary absolute
`NEWXAU_DESKTOP_USER_DATA_ROOT`.

## Promotion gates

Do not promote unsigned artifacts. Release promotion still requires:

1. clean non-admin Windows installation and uninstall testing;
2. offline/loopback backend lifecycle, restart, shutdown, and log inspection;
3. certificate-backed signing of executable, installer, and portable artifact;
4. Authenticode and SHA-256 verification after signing;
5. parity/cutover acceptance while the legacy dashboard remains available.
