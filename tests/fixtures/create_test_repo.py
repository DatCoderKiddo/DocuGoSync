"""
Creates a synthetic test repository ZIP for end-to-end testing.
Run: python tests/fixtures/create_test_repo.py
"""

import zipfile
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent
ZIP_PATH = OUTPUT_DIR / "test_repo.zip"

files = {
    "myproject/README.md": """\
# MyProject

## Authentication

Use `login(username, password)` to authenticate users.

Parameters:
- `username` - the user email
- `password` - the user password

## Logout

Call `logout(user_id)` to end a session.

## Configuration

Set the `SECRET_KEY` environment variable for token signing.
Default timeout: `connect(host, port=5432, timeout=30)`.
""",
    "myproject/src/auth.py": """\
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")

def login(username, password):
    \"\"\"Authenticate a user.\"\"\"
    return {"success": True, "user": username}

def logout(user_id):
    \"\"\"End a user session.\"\"\"
    return {"logged_out": user_id}
""",
    "myproject/src/db.py": """\
def connect(host, port=5432, timeout=30):
    \"\"\"Connect to the database.\"\"\"
    return {"host": host, "port": port}
""",
}

files_new = {
    "myproject/src/auth.py": """\
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
MFA_ENABLED = os.environ.get("MFA_ENABLED", "false")

def login(username, password, remember=False, mfa_code=None):
    \"\"\"Authenticate a user with optional MFA support.\"\"\"
    return {"success": True, "user": username}

def logout(user_id):
    \"\"\"End a user session.\"\"\"
    return {"logged_out": user_id}
""",
    "myproject/src/db.py": """\
def connect(host, port=5432, timeout=60):
    \"\"\"Connect to the database.\"\"\"
    return {"host": host, "port": port}
""",
}

# Write original repo ZIP
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for path, content in files.items():
        zf.writestr(path, content)

print(f"Created: {ZIP_PATH}")

# Write changed versions as separate files for diff testing
changed_dir = OUTPUT_DIR / "changed_files"
changed_dir.mkdir(exist_ok=True)

for rel_path, content in files.items():
    full = changed_dir / "original" / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)

for rel_path, content in files_new.items():
    full = changed_dir / "modified" / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)

print(f"Created original files: {changed_dir / 'original'}")
print(f"Created modified files: {changed_dir / 'modified'}")
print("Done. Run the backend and upload test_repo.zip to test drift detection.")
