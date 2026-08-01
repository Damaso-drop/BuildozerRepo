import json
import os
from uuid import uuid4
from datetime import datetime

class Database:
    def __init__(self):
        self.filename = 'barpos_data.json'
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
        if changed:
            self._save_data()

    def _init_defaults(self):
        changed = False
        
        if 'machine_id' not in self.data:
            self.data['machine_id'] = str(uuid4())[:16]
            changed = True

        if 'users' not in self.data:
            self.data['users'] = [{
                'username': 'admin',
                'password': '123',
                'role': 'admin'
            }]
            changed = True

        if 'categories' not in self.data:
            self.data['categories'] = [
                {'id': str(uuid4()), 'name': 'Bebidas'},
                {'id': str(uuid4()), 'name': 'Comida'},
                {'id': str(uuid4()), 'name': 'Petiscos'}
            ]
            changed = True

        if 'products' not in self.data:
            cats = {c['name']: c['id'] for c in self.data['categories']}
            self.data['products'] = [
                {'id': str(uuid4()), 'name': 'Coca Cola', 'price': 500, 'stock': 50,
                 'categoryId': cats.get('Bebidas', ''), 'priceTiers': []},
                {'id': str(uuid4()), 'name': 'Hambúrguer', 'price': 1200, 'stock': 20,
                 'categoryId': cats.get('Comida', ''), 'priceTiers': []},
                {'id': str(uuid4()), 'name': 'Cerveja', 'price': 400, 'stock': 100,
                 'categoryId': cats.get('Bebidas', ''), 'priceTiers': []}
            ]
            changed = True
            
        if 'sessions' not in self.data:
            self.data['sessions'] = []
            changed = True
            
        if 'transactions' not in self.data:
            self.data['transactions'] = []
            changed = True

        if changed:
            self._save_data()

    def get_machine_id(self):
        return self.data.get('machine_id', '')

    def get_license_key(self):
        return self.data.get('license_key')

    def set_license_key(self, key):
        self.data['license_key'] = key
        self._save_data()

    def authenticate(self, username, password):
        for u in self.data.get('users', []):
            if u['username'] == username and u['password'] == password:
                return u
        return None

    def verify_password(self, username, password):
        return self.authenticate(username, password) is not None
        
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

    def add_category(self, name):
        new_cat = {'id': str(uuid4()), 'name': name}
        self.data.setdefault('categories', []).append(new_cat)
        self._save_data()

    # --- DEBTS ---
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