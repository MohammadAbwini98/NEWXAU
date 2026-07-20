from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "vendor" / "Kronos"
HF_DIR = ROOT / "models" / "kronos_hf"
UPSTREAM_REPO = "https://github.com/shiyu-coder/Kronos.git"
DEFAULT_MODEL_ID = "NeoQuasar/Kronos-mini"
DEFAULT_TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-2k"


def _run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=str(cwd or ROOT), check=True)


def ensure_creator_repo() -> None:
    VENDOR_DIR.parent.mkdir(parents=True, exist_ok=True)
    if (VENDOR_DIR / ".git").exists():
        _run(["git", "pull", "--ff-only"], cwd=VENDOR_DIR)
        return
    if VENDOR_DIR.exists():
        print(f"Kronos vendor directory already exists without .git: {VENDOR_DIR}")
        return
    _run(["git", "clone", "--depth", "1", UPSTREAM_REPO, str(VENDOR_DIR)])


def download_snapshot(repo_id: str, destination_name: str) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        raise RuntimeError("Install huggingface_hub before downloading Kronos assets.") from exc

    target = HF_DIR / destination_name
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
        local_dir_use_symlinks=False,
    )
    return target


def main() -> None:
    model_id = os.getenv("KRONOS_DOWNLOAD_MODEL_ID", DEFAULT_MODEL_ID)
    tokenizer_id = os.getenv("KRONOS_DOWNLOAD_TOKENIZER_ID", DEFAULT_TOKENIZER_ID)

    ensure_creator_repo()
    model_path = download_snapshot(model_id, model_id.split("/")[-1])
    tokenizer_path = download_snapshot(tokenizer_id, tokenizer_id.split("/")[-1])

    print("Kronos creator repo: " + str(VENDOR_DIR))
    print("Kronos model: " + str(model_path))
    print("Kronos tokenizer: " + str(tokenizer_path))
    print("Set KRONOS_MODEL_ID=" + str(model_path.relative_to(ROOT)).replace("\\", "/"))
    print("Set KRONOS_TOKENIZER_ID=" + str(tokenizer_path.relative_to(ROOT)).replace("\\", "/"))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:
        print(f"Kronos download failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
