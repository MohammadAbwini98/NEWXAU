# Windows packaging gate

NEWXAU uses a private-runtime packaging model so the installed application does
not depend on a machine-wide Python installation.

## Required release input

Stage a validated x64 Windows runtime at:

```text
desktop/runtime/python/
  python.exe
  python312.dll
  Lib/
  Lib/site-packages/
```

The environment must match the Python and native-library versions used for the
approved backend build. It must include FastAPI/Uvicorn, PostgreSQL support,
NumPy/pandas/scikit-learn, PyTorch, LightGBM, ONNX Runtime, and the NEWXAU
package or an importable source path.

## Release commands

```powershell
npm ci
npm run runtime:verify
npm run package:dir
npm run package:win
```

Packaging is expected to run with Node 22.12 or newer. The unpacked app must be
smoke-tested from a clean Windows account before NSIS/portable artifacts are
promoted.

## Artifact policy

Model artifacts and the private runtime are large signed release inputs. They
must not be committed to Git. The builder includes `models/` and the staged
private runtime in the Windows artifact; a future signed model-pack split can
replace this only after hash and version validation exists.
