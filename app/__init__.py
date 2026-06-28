# filepath: app/__init__.py
# -*- coding: utf-8 -*-

from flask import Flask
import os
import sys

# Determine base and root directories dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))

# Create Flask app instance directing to root's templates and static folder
app = Flask(
    __name__, 
    template_folder=os.path.join(ROOT_DIR, 'templates'),
    static_folder=os.path.join(ROOT_DIR, 'static')
)
app.secret_key = 'super_secret_esports_bot_panel_key_2025_neon_chassis'

# Initialize MongoDB data sync directly to local SQLite DB on startup
try:
    print("[SYSTEM] Fetching latest data from MongoDB to SQLite...")
    import mongo_sync
    mongo_sync.init_sqlite()
    mongo_sync.pull_all_from_mongo()
except Exception as e:
    print(f"[SYSTEM ERROR] SQLite Init/Pull failed: {e}")

# Expose shared methods & sessions for safe external module imports (like bot_manager.py)
from app.helpers import sync_friends_to_bot_admins, SYNCED_BOTS_SESSION

# Register blueprints to keep code separated
from app.routes_auth import auth_bp
from app.routes_bots import bots_bp
from app.routes_garena import garena_bp

app.register_blueprint(auth_bp)
app.register_blueprint(bots_bp)
app.register_blueprint(garena_bp)
