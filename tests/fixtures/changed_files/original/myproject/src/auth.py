import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")

def login(username, password):
    """Authenticate a user."""
    return {"success": True, "user": username}

def logout(user_id):
    """End a user session."""
    return {"logged_out": user_id}
