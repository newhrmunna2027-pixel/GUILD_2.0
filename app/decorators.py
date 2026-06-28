# filepath: app/decorators.py
# -*- coding: utf-8 -*-

from functools import wraps
from flask import session, redirect, url_for, jsonify

def login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'username' not in session: 
            return redirect(url_for('auth_bp.login'))
        return await f(*args, **kwargs)
    return decorated_function

def bp_login_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({"success": False, "msg": "Unauthorized access. Session expired."}), 401
        return await f(*args, **kwargs)
    return decorated_function
