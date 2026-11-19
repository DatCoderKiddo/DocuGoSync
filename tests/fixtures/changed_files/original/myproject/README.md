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
