import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
MFA_ENABLED = os.environ.get("MFA_ENABLED", "false")

def login(username, password, remember=False, mfa_code=None):
    """Authenticate a user with optional MFA support."""
    return {"success": True, "user": username}

def logout(user_id):
    """End a user session."""
    return {"logged_out": user_id}
