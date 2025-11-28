from __future__ import annotations

from functools import wraps

from flask import abort, current_app
from flask_login import current_user


def admin_required(f):
    """Decorator to require admin role for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip authentication in test mode
        if current_app.config.get("LOGIN_DISABLED", False):
            return f(*args, **kwargs)
        
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
