"""
DocuGoSync end-to-end verification script.
Run: python verify.py
"""

from backend.main import app
from fastapi.testclient import TestClient
import time

client = TestClient(app)

print("=== DocuGoSync End-to-End Verification ===\n")

# 1. Health check
r = client.get("/api/health")
print(f"1. Health: {r.json()}")

# 2. Upload test repository
with open("tests/fixtures/test_repo.zip", "rb") as f:
    r = client.post(
        "/api/repositories/upload",
        files={"file": ("test_repo.zip", f, "application/zip")},
    )
repo = r.json()
repo_id = repo["id"]
print(f"2. Uploaded repo: {repo['name']} (id={repo_id[:8]}...)")

# 3. Wait for indexing
for i in range(30):
    r = client.get(f"/api/repositories/{repo_id}")
    status = r.json()["index_status"]
    if status == "ready":
        break
    time.sleep(0.3)

stats = r.json()["stats"]
print(
    f"3. Indexed: {stats['symbols']} symbols, "
    f"{stats['doc_sections']} sections, "
    f"{stats['mappings']} mappings"
)

# 4. Detect drift
old_code = open("tests/fixtures/changed_files/original/myproject/src/auth.py").read()
new_code = open("tests/fixtures/changed_files/modified/myproject/src/auth.py").read()

r = client.post(
    f"/api/analysis/{repo_id}/files",
    json={
        "files": [
            {
                "path": "myproject/src/auth.py",
                "old_content": old_code,
                "new_content": new_code,
            }
        ],
        "doc_file_path": "myproject/README.md",
    },
)
result = r.json()
print(f"4. Drift detection: {result['issues_found']} issue(s) found\n")

for issue in result["issues"]:
    print(f"   [{issue['severity'].upper()}] {issue['description'][:90]}")
    print(f"   Evidence code: {issue['evidence_code'][:70]}")
    print(f"   Outdated doc:  {issue['evidence_doc'][:70]}")
    print(f"   Correction:    {issue['suggested_correction'][:70]}")
    print(f"   Confidence:    {issue['confidence']:.0%}")
    print()

# 5. Approve
if result["issues"]:
    issue_id = result["issues"][0]["id"]
    r = client.patch(f"/api/drift/{issue_id}/status", json={"status": "approved"})
    print(f"5. Approved issue: status={r.json()['status']}")

# 6. List all issues
r = client.get("/api/drift")
print(f"6. Total issues in DB: {len(r.json())}")

print("\n=== All verification steps completed successfully ===")
