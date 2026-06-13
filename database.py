import os
import sqlite3
from datetime import datetime
from flask_bcrypt import generate_password_hash, check_password_hash

DB_FILE = os.environ.get('DATABASE_PATH', 'barcode_system.db')
DEFAULT_ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
DEFAULT_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin12345')


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
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
            is_admin INTEGER DEFAULT 0,
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
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, barcode)
        )
    ''')
    cursor.execute('PRAGMA table_info(users)')
    user_columns = {row['name'] for row in cursor.fetchall()}
    if 'is_admin' not in user_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')

    cursor.execute('PRAGMA foreign_key_list(items)')
    # Existing SQLite tables cannot be altered to add ON DELETE CASCADE cheaply; app-level deletes still clean up.
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_user_name ON items(user_id, name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_user_barcode ON items(user_id, barcode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)')
    conn.commit()
    conn.close()


def ensure_admin_user():
    if not DEFAULT_ADMIN_PASSWORD:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (DEFAULT_ADMIN_USERNAME,))
    if cursor.fetchone():
        conn.close()
        return
    pw_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD).decode('utf-8')
    cursor.execute('INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, 1)',
                   (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL, pw_hash))
    conn.commit()
    conn.close()


def create_user(username, email, password, is_admin=False):
    conn = get_connection()
    cursor = conn.cursor()
    pw_hash = generate_password_hash(password).decode('utf-8')
    try:
        cursor.execute('INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
                       (username, email, pw_hash, 1 if is_admin else 0))
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        return False, 'Username or email already exists'
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
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute('''
            INSERT INTO items (user_id, barcode, name, category, quantity, location, notes, added_date, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, barcode, name, category, max(quantity, 1), location, notes, now, now))
        conn.commit()
        return {'success': True, 'message': 'Item added'}
    except sqlite3.IntegrityError:
        cursor.execute('UPDATE items SET quantity = quantity + ?, last_updated = ? WHERE user_id = ? AND barcode = ?',
                       (max(quantity, 1), now, user_id, barcode))
        conn.commit()
        return {'success': True, 'message': 'Quantity increased'}
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
    like = f'%{query}%'
    cursor.execute('''
        SELECT * FROM items
        WHERE user_id = ? AND (name LIKE ? OR barcode LIKE ? OR category LIKE ? OR location LIKE ?)
        ORDER BY name COLLATE NOCASE
    ''', (user_id, like, like, like, like))
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def get_all_items(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE user_id = ? ORDER BY name COLLATE NOCASE', (user_id,))
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def update_item(item_id, user_id, name, category, quantity, location, notes):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        UPDATE items SET name=?, category=?, quantity=?, location=?, notes=?, last_updated=?
        WHERE id=? AND user_id=?
    ''', (name, category, max(quantity, 1), location, notes, now, item_id, user_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()
    return updated > 0


def delete_item(item_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM items WHERE id = ? AND user_id = ?', (item_id, user_id))
    conn.commit()
    conn.close()


def get_admin_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM items')
    item_count, total_quantity = cursor.fetchone()
    cursor.execute('SELECT COUNT(DISTINCT category) FROM items')
    categories = cursor.fetchone()[0]
    conn.close()
    return {'users': users, 'items': item_count, 'quantity': total_quantity, 'categories': categories}


def get_all_users_with_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.email, u.is_admin, u.created_at,
               COUNT(i.id) AS item_count, COALESCE(SUM(i.quantity), 0) AS total_quantity
        FROM users u
        LEFT JOIN items i ON i.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''')
    users = cursor.fetchall()
    conn.close()
    return [dict(row) for row in users]


def get_recent_items(limit=50):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.*, u.username
        FROM items i
        JOIN users u ON u.id = i.user_id
        ORDER BY i.last_updated DESC
        LIMIT ?
    ''', (limit,))
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def set_user_admin(user_id, is_admin):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_admin = ? WHERE id = ?', (1 if is_admin else 0, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM items WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
