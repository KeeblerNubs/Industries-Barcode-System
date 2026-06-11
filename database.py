import sqlite3
from datetime import datetime
from flask_bcrypt import generate_password_hash, check_password_hash

DB_FILE = "barcode_system.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            barcode TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Uncategorized',
            quantity INTEGER DEFAULT 1,
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            added_date TEXT DEFAULT (datetime('now', 'localtime')),
            last_updated TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, barcode)
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username, email, password):
    conn = get_connection()
    cursor = conn.cursor()
    pw_hash = generate_password_hash(password).decode('utf-8')
    try:
        cursor.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                       (username, email, pw_hash))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, "Username or email already exists"
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)

def add_item(user_id, barcode, name, category, quantity, location, notes):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute('''
            INSERT INTO items (user_id, barcode, name, category, quantity, location, notes, added_date, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, barcode, name, category, quantity, location, notes, now, now))
        conn.commit()
        return {"success": True, "message": "Item added"}
    except sqlite3.IntegrityError:
        cursor.execute('''
            UPDATE items SET quantity = quantity + 1, last_updated = ?
            WHERE user_id = ? AND barcode = ?
        ''', (now, user_id, barcode))
        conn.commit()
        return {"success": True, "message": "Quantity increased"}
    finally:
        conn.close()

def search_item(user_id, barcode):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE user_id = ? AND barcode = ?', (user_id, barcode))
    item = cursor.fetchone()
    conn.close()
    return dict(item) if item else None

def search_items(user_id, query):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM items
        WHERE user_id = ? AND (name LIKE ? OR barcode LIKE ? OR category LIKE ?)
        ORDER BY name
    ''', (user_id, f'%{query}%', f'%{query}%', f'%{query}%'))
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]

def get_all_items(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE user_id = ? ORDER BY name', (user_id,))
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]

def update_item(item_id, user_id, name, category, quantity, location, notes):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE items SET name=?, category=?, quantity=?, location=?, notes=?, last_updated=?
        WHERE id=? AND user_id=?
    ''', (name, category, quantity, location, notes, now, item_id, user_id))
    conn.commit()
    conn.close()

def delete_item(item_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM items WHERE id = ? AND user_id = ?', (item_id, user_id))
    conn.commit()
    conn.close()
