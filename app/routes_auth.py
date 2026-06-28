# filepath: app/routes_auth.py
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import random
import threading
import mongo_sync
from app.database import get_db
from app.decorators import login_required

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        async with get_db() as db:
            async with db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)) as cursor:
                user = await cursor.fetchone()
                if user:
                    session['username'], session['role'] = user['username'], user['role']
                    return redirect(url_for('auth_bp.index'))
        return render_template('login.html', error="Invalid Username or Password!")
    if 'username' in session: return redirect(url_for('auth_bp.index'))
    return render_template('login.html')

@auth_bp.route('/logout')
async def logout():
    session.clear()
    return redirect(url_for('auth_bp.login'))

@auth_bp.route('/')
@login_required
async def index():
    return render_template('index.html', username=session.get('username'), role=session.get('role'))

@auth_bp.route('/api/users', methods=['GET'])
@login_required
async def get_users_list():
    try:
        if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Access Denied"})
        user_list = []
        async with get_db() as db:
            async with db.execute("SELECT * FROM users") as cursor:
                users = await cursor.fetchall()
            for u in users:
                async with db.execute("SELECT COUNT(*) FROM bots WHERE folder=?", (u['username'],)) as bcur:
                    bot_count = (await bcur.fetchone())[0]
                user_list.append({"username": u['username'], "password": u['password'], "role": u['role'], "uid": u['uid'], "bots": bot_count})
        return jsonify({"status": "success", "users": user_list})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@auth_bp.route('/api/users/action', methods=['POST'])
@login_required
async def manage_users():
    try:
        if session.get('role') != 'owner': return jsonify({"status": "error", "msg": "Access Denied"})
        data = request.json
        action = data.get('action')
        async with get_db() as db:
            if action == 'add':
                uname = data.get('username')
                async with db.execute("SELECT username FROM users WHERE username=?", (uname,)) as cur:
                    if await cur.fetchone(): return jsonify({"status": "error", "msg": "User already exists!"})
                new_uid = str(random.randint(10000, 99999))
                await db.execute("INSERT INTO users (username, password, role, uid) VALUES (?, ?, ?, ?)", (uname, data.get('password'), data.get('role'), new_uid))
            elif action == 'edit':
                old_uname = data.get('old_username')
                new_uname = data.get('new_username')
                if old_uname != new_uname:
                    async with db.execute("SELECT username FROM users WHERE username=?", (new_uname,)) as cur:
                        if await cur.fetchone(): return jsonify({"status": "error", "msg": "Username already taken!"})
                    await db.execute("UPDATE users SET username=?, password=?, role=? WHERE username=?", (new_uname, data.get('password'), data.get('role'), old_uname))
                    await db.execute("UPDATE bots SET folder=?, owner=? WHERE folder=?", (new_uname, new_uname, old_uname))
                else:
                    await db.execute("UPDATE users SET password=?, role=? WHERE username=?", (data.get('password'), data.get('role'), old_uname))
            elif action == 'delete':
                uname = data.get('username')
                if uname == session.get('username'): return jsonify({"status": "error", "msg": "Cannot delete yourself!"})
                await db.execute("DELETE FROM users WHERE username=?", (uname,))
            await db.commit()
        
        threading.Thread(target=mongo_sync.push_user_to_mongo).start()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})
