import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import database as db


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    class User(UserMixin):
        def __init__(self, user_dict):
            self.id = user_dict['id']
            self.username = user_dict['username']
            self.email = user_dict.get('email', '')
            self.is_admin = bool(user_dict.get('is_admin', 0))

    @login_manager.user_loader
    def load_user(user_id):
        user_data = db.get_user_by_id(int(user_id))
        return User(user_data) if user_data else None

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.is_admin:
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user_data = db.get_user_by_username(username)
            if not user_data or not db.verify_password(password, user_data['password_hash']):
                flash('Invalid credentials', 'error')
                return render_template('login.html')
            login_user(User(user_data), remember=True)
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            if not username or not email or not password:
                flash('All fields required', 'error')
            elif password != confirm:
                flash('Passwords do not match', 'error')
            elif len(password) < 8:
                flash('Password must be at least 8 characters', 'error')
            else:
                success, result = db.create_user(username, email, password)
                if success:
                    flash('Registration successful. Please log in.', 'success')
                    return redirect(url_for('login'))
                flash(result, 'error')
        return render_template('register.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html', username=current_user.username, is_admin=current_user.is_admin)

    @app.route('/admin')
    @admin_required
    def admin():
        stats = db.get_admin_stats()
        users = db.get_all_users_with_stats()
        items = db.get_recent_items(limit=50)
        return render_template('admin.html', stats=stats, users=users, items=items)

    @app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
    @admin_required
    def admin_toggle_user(user_id):
        if user_id == current_user.id:
            flash('You cannot change your own admin access.', 'error')
        else:
            db.set_user_admin(user_id, request.form.get('is_admin') == '1')
            flash('User access updated.', 'success')
        return redirect(url_for('admin'))

    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_user(user_id):
        if user_id == current_user.id:
            flash('You cannot delete your own account.', 'error')
        else:
            db.delete_user(user_id)
            flash('User deleted.', 'success')
        return redirect(url_for('admin'))

    @app.route('/api/items')
    @login_required
    def api_get_items():
        search = request.args.get('search', '').strip()
        items = db.search_items(current_user.id, search) if search else db.get_all_items(current_user.id)
        return jsonify({'items': items, 'total': len(items)})

    @app.route('/api/items/lookup')
    @login_required
    def api_lookup():
        barcode = request.args.get('barcode', '').strip()
        if not barcode:
            return jsonify({'found': False}), 400
        item = db.search_item(current_user.id, barcode)
        return jsonify({'found': bool(item), 'item': item})

    @app.route('/api/items', methods=['POST'])
    @login_required
    def api_add():
        data = request.get_json(silent=True) or {}
        if not data.get('barcode') or not data.get('name'):
            return jsonify({'success': False, 'error': 'Barcode and name required'}), 400
        result = db.add_item(current_user.id, data['barcode'].strip(), data['name'].strip(),
                             data.get('category', 'Uncategorized'), int(data.get('quantity', 1)),
                             data.get('location', '').strip(), data.get('notes', '').strip())
        if result['success']:
            item = db.search_item(current_user.id, data['barcode'].strip())
            return jsonify({'success': True, 'message': result['message'], 'item': item}), 201
        return jsonify(result), 400

    @app.route('/api/items/<int:item_id>', methods=['PUT'])
    @login_required
    def api_update(item_id):
        data = request.get_json(silent=True) or {}
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Name is required'}), 400
        updated = db.update_item(item_id, current_user.id, data['name'].strip(),
                                 data.get('category', 'Uncategorized'), int(data.get('quantity', 1)),
                                 data.get('location', '').strip(), data.get('notes', '').strip())
        if not updated:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        return jsonify({'success': True, 'message': 'Item updated'})

    @app.route('/api/items/<int:item_id>', methods=['DELETE'])
    @login_required
    def api_delete(item_id):
        db.delete_item(item_id, current_user.id)
        return jsonify({'success': True, 'message': 'Item deleted'})

    db.init_db()
    db.ensure_admin_user()
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
