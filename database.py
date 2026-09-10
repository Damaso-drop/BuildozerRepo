import json
import os
from uuid import uuid4
from datetime import datetime

try:
    from kivy.utils import platform
except ImportError:
    platform = 'linux'


def _get_data_dir():
    """Return a private, per-installation storage directory.

    On Android this is the app's internal 'files' directory. The OS
    guarantees this directory is empty on every fresh install and wipes
    it on uninstall — it is NOT part of the APK's bundled assets/source.
    This is what stops a build from accidentally shipping a
    pre-populated data file to every device that installs the app.
    """
    if platform == 'android':
        try:
            from android.storage import app_storage_path
            return app_storage_path()
        except Exception:
            pass
    # Desktop / dev fallback: keep behaving like before.
    return os.path.dirname(os.path.abspath(__file__))


class Database:
    def __init__(self):
        self.filename = os.path.join(_get_data_dir(), 'barpos_data.json')
        self.data = self._load_data()
        self._init_defaults()
        self._migrate()

    def _load_data(self):
        if not os.path.exists(self.filename):
            return {}
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except:
            return {}

    def _save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)

    def _migrate(self):
        changed = False
        for p in self.data.get('products', []):
            if 'priceTiers' not in p:
                p['priceTiers'] = []
                changed = True
        if 'debts' not in self.data:
            self.data['debts'] = []
            changed = True
        if 'license_data' not in self.data:
            self.data['license_data'] = {}
            changed = True
        if changed:
            self._save_data()

    def _init_defaults(self):
        changed = False

        if 'machine_id' not in self.data:
            self.data['machine_id'] = str(uuid4())[:16]
            changed = True

        # A single default admin so the very first login is possible.
        # The user is expected to create a new admin with a strong
        # password and then delete this default one.
        if 'users' not in self.data:
            self.data['users'] = [{
                'username': 'admin',
                'password': '123',
                'role': 'admin'
            }]
            changed = True

        # IMPORTANT: no default categories or products.
        # Fresh installs start completely empty; the user creates
        # everything from the admin panel.
        if 'categories' not in self.data:
            self.data['categories'] = []
            changed = True

        if 'products' not in self.data:
            self.data['products'] = []
            changed = True

        if 'sessions' not in self.data:
            self.data['sessions'] = []
            changed = True

        if 'transactions' not in self.data:
            self.data['transactions'] = []
            changed = True

        if 'debts' not in self.data:
            self.data['debts'] = []
            changed = True

        if 'license_data' not in self.data:
            self.data['license_data'] = {}
            changed = True

        if changed:
            self._save_data()

    # ------------------------------------------------------------------ license
    def get_machine_id(self):
        return self.data.get('machine_id', '')

    def set_machine_id(self, machine_id):
        self.data['machine_id'] = machine_id
        self._save_data()

    def get_license_key(self):
        return self.data.get('license_data', {}).get('key')

    def set_license_key(self, key):
        self.data.setdefault('license_data', {})['key'] = key
        self._save_data()

    def get_license_last_seen(self):
        return self.data.get('license_data', {}).get('last_seen')

    def update_license_last_seen(self, timestamp):
        self.data.setdefault('license_data', {})['last_seen'] = timestamp
        self._save_data()

    # ------------------------------------------------------------------ auth
    def authenticate(self, username, password):
        for u in self.data.get('users', []):
            if u['username'] == username and u['password'] == password:
                return u
        return None

    def verify_password(self, username, password):
        return self.authenticate(username, password) is not None

    # ------------------------------------------------------------------ users
    def username_exists(self, username):
        return any(u['username'] == username for u in self.data.get('users', []))

    def add_user(self, username, password, role='employee'):
        """Add a new user. Returns (ok, message).
        Rules:
          - username must be non-empty and unique
          - password must be non-empty
          - if role == 'admin', password must NOT equal the default '123'
        """
        username = (username or '').strip()
        password = password or ''
        if not username or not password:
            return False, "Preencha todos os campos"
        if self.username_exists(username):
            return False, "Nome de usuário já existe"
        if role == 'admin' and password == '123':
            return False, "Senha do administrador não pode ser a padrão (123)"
        self.data.setdefault('users', []).append({
            'username': username,
            'password': password,
            'role': role
        })
        self._save_data()
        return True, "Usuário criado com sucesso"

    def remove_user(self, username):
        """Remove a user, but never allow removing the last admin.
        Returns (ok, message).
        """
        target = next((u for u in self.data.get('users', [])
                       if u['username'] == username), None)
        if not target:
            return False, "Usuário não encontrado"
        if target['role'] == 'admin':
            remaining_admins = [
                u for u in self.data['users']
                if u['role'] == 'admin' and u['username'] != username
            ]
            if not remaining_admins:
                return False, "É preciso manter pelo menos um administrador"
        self.data['users'] = [u for u in self.data['users']
                              if u['username'] != username]
        self._save_data()
        return True, "Usuário removido"

    # ------------------------------------------------------------------ catalog
    def get_categories(self):
        return self.data.get('categories', [])

    def get_products(self):
        return self.data.get('products', [])

    def update_stock(self, product_id, change):
        for p in self.data['products']:
            if p['id'] == product_id:
                if p['stock'] + change < 0:
                    return False
                p['stock'] += change
                self._save_data()
                return True
        return False

    def add_category(self, name):
        new_cat = {'id': str(uuid4()), 'name': name}
        self.data.setdefault('categories', []).append(new_cat)
        self._save_data()

    # ------------------------------------------------------------------ sessions
    def get_sessions(self):
        return self.data.get('sessions', [])

    def save_session(self, session_data):
        self.data['sessions'] = [s for s in self.data['sessions']
                                 if s['tableName'] != session_data['tableName']]
        self.data['sessions'].append(session_data)
        self._save_data()

    def remove_session(self, table_name):
        self.data['sessions'] = [s for s in self.data['sessions']
                                 if s['tableName'] != table_name]
        self._save_data()

    # ------------------------------------------------------------------ checkout
    def checkout(self, table_name, total, items, paid=None, change=None):
        t = {
            'id': str(uuid4()),
            'tableName': table_name,
            'totalAmount': total,
            'timestamp': datetime.now().isoformat(),
            'items': items
        }
        if paid is not None:
            t['paid'] = paid
        if change is not None:
            t['change'] = change
        self.data['transactions'].append(t)
        self.remove_session(table_name)
        self._save_data()

    # ------------------------------------------------------------------ debts
    def add_debt(self, debt):
        debt['id'] = str(uuid4())
        debt['timestamp'] = datetime.now().isoformat()
        self.data['debts'].append(debt)
        self._save_data()

    def get_debts(self):
        return self.data.get('debts', [])

    def remove_debt(self, debt_id):
        self.data['debts'] = [d for d in self.data['debts'] if d['id'] != debt_id]
        self._save_data()


db = Database()