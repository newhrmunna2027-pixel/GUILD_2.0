# filepath: app/database.py
# -*- coding: utf-8 -*-

import os
import aiosqlite
from contextlib import asynccontextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
DB_PATH = os.path.join(ROOT_DIR, 'config', 'database.db')

@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH, timeout=30.0)
    try:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout = 30000;")
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()
