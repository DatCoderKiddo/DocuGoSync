"""
Repository crawler — discovers and reads source and documentation files.

Supports:
  - Local filesystem path
  - ZIP archive (extracted to temp dir)
  - GitHub URL (cloned via git or fetched via API)
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ── File classification ───────────────────────────────────────────────────────

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
DOC_FILENAMES = {"readme", "changelog", "contributing", "license", "authors", "history", "api"}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".cs", ".rb", ".php",
    ".c", ".cpp", ".h", ".hpp",
}

CONFIG_EXTENSIONS = {".yaml", ".yml", ".toml", ".json", ".ini", ".cfg", ".env"}
CONFIG_FILENAMES = {"setup.py", "setup.cfg", "pyproject.toml", "package.json",
                    "requirements.txt", "cargo.toml", "go.mod"}

IGNORE_DIRS = {
    ".git", ".github", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache", "coverage",
    ".eggs", "*.egg-info",
}

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


@dataclass
class DiscoveredFile:
    relative_path: str
    absolute_path: str
    file_type: str           # doc | code | config | other
    size_bytes: int


@dataclass
class RepoCrawlResult:
    root_path: str
    files: list[DiscoveredFile] = field(default_factory=list)
    readme_path: Optional[str] = None      # relative path of primary README
    temp_dir: Optional[str] = None         # if we extracted a ZIP, clean this up

    @property
    def doc_files(self) -> list[DiscoveredFile]:
        return [f for f in self.files if f.file_type == "doc"]

    @property
    def code_files(self) -> list[DiscoveredFile]:
        return [f for f in self.files if f.file_type == "code"]

    def cleanup(self) -> None:
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)


# ── Classifier ────────────────────────────────────────────────────────────────

def classify_file(path: Path) -> str:
    name_lower = path.stem.lower()
    ext = path.suffix.lower()

    if ext in DOC_EXTENSIONS:
        return "doc"
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in CONFIG_EXTENSIONS or name_lower in CONFIG_FILENAMES:
        return "config"
    return "other"


def _should_ignore_dir(name: str) -> bool:
    return name in IGNORE_DIRS or name.startswith(".")


# ── Core crawler ──────────────────────────────────────────────────────────────

class RepoCrawler:
    def crawl_path(self, root: str) -> RepoCrawlResult:
        root_path = Path(root).resolve()
        result = RepoCrawlResult(root_path=str(root_path))
        readme: Optional[Path] = None

        for dirpath, dirnames, filenames in os.walk(root_path):
            # Prune ignored dirs in-place
            dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                try:
                    size = fpath.stat().st_size
                except OSError:
                    continue

                if size > MAX_FILE_SIZE:
                    continue

                rel = str(fpath.relative_to(root_path)).replace("\\", "/")
                ftype = classify_file(fpath)
                discovered = DiscoveredFile(
                    relative_path=rel,
                    absolute_path=str(fpath),
                    file_type=ftype,
                    size_bytes=size,
                )
                result.files.append(discovered)

                if fpath.name.lower() == "readme.md" and readme is None:
                    readme = fpath

        if readme:
            result.readme_path = str(readme.relative_to(root_path)).replace("\\", "/")

        return result

    def crawl_zip(self, zip_path: str) -> RepoCrawlResult:
        tmp = tempfile.mkdtemp(prefix="docugosync_")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        # Find actual root (zip may have a single top-level folder)
        entries = list(Path(tmp).iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            root = str(entries[0])
        else:
            root = tmp

        result = self.crawl_path(root)
        result.temp_dir = tmp
        return result

    async def crawl_github(self, repo_url: str, branch: str = "main", token: str = "") -> RepoCrawlResult:
        """Clone or download a GitHub repository and crawl it."""
        import subprocess

        tmp = tempfile.mkdtemp(prefix="docugosync_gh_")
        try:
            # Try git clone first
            env = os.environ.copy()
            if token:
                # Inject token into URL
                url = repo_url
                if url.startswith("https://github.com/"):
                    url = url.replace("https://", f"https://{token}@")
                env["GIT_TERMINAL_PROMPT"] = "0"
                cmd = ["git", "clone", "--depth=1", f"--branch={branch}", url, tmp]
            else:
                env["GIT_TERMINAL_PROMPT"] = "0"
                cmd = ["git", "clone", "--depth=1", f"--branch={branch}", repo_url, tmp]

            proc = subprocess.run(cmd, capture_output=True, timeout=120, env=env)
            if proc.returncode != 0:
                # Try default branch
                cmd2 = ["git", "clone", "--depth=1", repo_url, tmp]
                proc2 = subprocess.run(cmd2, capture_output=True, timeout=120, env=env)
                if proc2.returncode != 0:
                    raise RuntimeError(f"git clone failed: {proc2.stderr.decode()}")

            # Find actual root inside clone
            entries = [e for e in Path(tmp).iterdir() if not e.name.startswith(".")]
            if len(entries) == 1 and entries[0].is_dir():
                root = str(entries[0])
            else:
                root = tmp

            result = self.crawl_path(root)
            result.temp_dir = tmp
            return result

        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
