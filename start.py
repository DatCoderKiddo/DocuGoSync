"""
DocuGoSync startup helper.
Run: python start.py

Starts the backend API server.
The frontend must be started separately: cd frontend && npm run dev
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("Starting DocuGoSync backend on http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    print()
    print("To start the frontend:")
    print("  cd frontend && npm run dev")
    print("  Then open http://localhost:5173")
    print()
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000",
    ])
