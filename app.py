# filepath: app.py
# -*- coding: utf-8 -*-

import os
import sys

# Ensure root directory is added in Python execution paths to prevent resolution failures
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app
import mongo_sync

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 20881))
    app.run(host='0.0.0.0', port=port, debug=False)
