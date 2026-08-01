import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.uix.recycleview import RecycleView
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.dropdown import DropDown
from kivy.uix.widget import Widget
from kivy.uix.progressbar import ProgressBar
from kivy.properties import StringProperty, NumericProperty, ObjectProperty, ListProperty, BooleanProperty
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse
from uuid import uuid4
from datetime import datetime, timedelta
import threading
import math

from database import db
from styles import Theme

# --- CUSTOM WIDGETS ---

class RoundedButton(Button):
    bg_color = ListProperty([0, 0, 0, 0])

class IconButton(Button):
    bg_color = ListProperty([0, 0, 0, 0])
    icon_source = StringProperty("")
    shadow_color = ListProperty([0, 0, 0, 0])
    shadow_offset = ListProperty([0, 0])

class CategoryButton(Button):
    bg_color = ListProperty([0, 0, 0, 0])
    text_color = ListProperty([1, 1, 1, 1])

class ReportFilterButton(Button):
    group = StringProperty("")
    selected = BooleanProperty(False)
    bg_color = ListProperty([0, 0, 0, 0])

class IconWidget(Widget):
    """
    Lightweight vector-drawn icon widget. No external image/font assets required.

    Usage in .kv:
        IconWidget:
            size_hint: None, None
            size: dp(20), dp(20)
            icon_name: 'trash'
            icon_color: C_WHITE

    --- Upgrading to a real icon font (e.g. FontAwesome) later ---
    If you ever add a FontAwesome/Material-Icons .ttf to this project, the cleanest
    swap is to register it once:
        from kivy.core.text import LabelBase
        LabelBase.register(name='FA', fn_regular='assets/fonts/fa-solid-900.ttf')
    and then use a plain Label with font_name: 'FA' and text: '\uf1f8' (trash),
    '\uf044' (edit), '\uf00d' (close), '\uf067' (plus), '\uf2f6' (logout), etc.
    Keeping icon_name as the public API here means call sites in the .kv file
    below would not need to change if you switch the renderer later.
    """
    icon_name = StringProperty('')
    icon_color = ListProperty([1, 1, 1, 1])
    line_width = NumericProperty(dp(1.6))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw,
                  icon_name=self._redraw, icon_color=self._redraw,
                  line_width=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _redraw(self, *args):
        self.canvas.clear()
        if not self.icon_name or self.width <= 0 or self.height <= 0:
            return
        method = getattr(self, '_draw_' + self.icon_name.replace('-', '_'), None)
        if not method:
            return
        with self.canvas:
            Color(*self.icon_color)
            method()

    def _box(self, pad=0.18):
        x, y, w, h = self.x, self.y, self.width, self.height
        s = min(w, h)
        cx, cy = x + w / 2.0, y + h / 2.0
        r = s / 2.0 * (1 - pad)
        return cx, cy, r

    # --- icon drawers ---

    def _draw_trash(self):
        cx, cy, r = self._box(0.12)
        lw = self.line_width
        Line(points=[cx - r, cy + r * 0.55, cx + r, cy + r * 0.55], width=lw, cap='round')
        Line(points=[cx - r * 0.35, cy + r * 0.55, cx - r * 0.25, cy + r * 0.85,
                     cx + r * 0.25, cy + r * 0.85, cx + r * 0.35, cy + r * 0.55],
             width=lw, joint='round', cap='round')
        Line(rounded_rectangle=(cx - r * 0.75, cy - r, r * 1.5, r * 1.5, r * 0.15), width=lw)
        Line(points=[cx - r * 0.3, cy - r * 0.7, cx - r * 0.3, cy + r * 0.3], width=lw * 0.8)
        Line(points=[cx + r * 0.3, cy - r * 0.7, cx + r * 0.3, cy + r * 0.3], width=lw * 0.8)

    def _draw_edit(self):
        cx, cy, r = self._box(0.15)
        lw = self.line_width
        Line(points=[cx - r * 0.9, cy - r * 0.9, cx + r * 0.5, cy + r * 0.6],
             width=lw * 1.4, cap='round')
        Line(points=[cx + r * 0.5, cy + r * 0.6, cx + r * 0.9, cy + r * 0.9, cx + r * 0.6, cy + r * 0.5],
             width=lw, joint='round', cap='round')
        Line(points=[cx - r * 0.95, cy - r * 0.95, cx - r * 0.75, cy - r * 0.6, cx - r * 0.6, cy - r * 0.75],
             width=lw, joint='round', cap='round')

    def _draw_plus(self):
        cx, cy, r = self._box(0.2)
        lw = self.line_width * 1.3
        Line(points=[cx - r, cy, cx + r, cy], width=lw, cap='round')
        Line(points=[cx, cy - r, cx, cy + r], width=lw, cap='round')

    def _draw_minus(self):
        cx, cy, r = self._box(0.2)
        lw = self.line_width * 1.3
        Line(points=[cx - r, cy, cx + r, cy], width=lw, cap='round')

    def _draw_close(self):
        cx, cy, r = self._box(0.24)
        lw = self.line_width * 1.2
        Line(points=[cx - r, cy - r, cx + r, cy + r], width=lw, cap='round')
        Line(points=[cx - r, cy + r, cx + r, cy - r], width=lw, cap='round')

    def _draw_back(self):
        cx, cy, r = self._box(0.2)
        lw = self.line_width * 1.3
        Line(points=[cx + r * 0.6, cy - r, cx - r * 0.6, cy, cx + r * 0.6, cy + r],
             width=lw, joint='round', cap='round')

    def _draw_chevron_down(self):
        cx, cy, r = self._box(0.3)
        lw = self.line_width * 1.2
        Line(points=[cx - r, cy + r * 0.4, cx, cy - r * 0.5, cx + r, cy + r * 0.4],
             width=lw, joint='round', cap='round')

    def _draw_tables(self):
        cx, cy, r = self._box(0.18)
        lw = self.line_width
        g = r * 0.22
        s = r
        Line(rectangle=(cx - s, cy + g / 2, s - g / 2, s - g / 2), width=lw)
        Line(rectangle=(cx + g / 2, cy + g / 2, s - g / 2, s - g / 2), width=lw)
        Line(rectangle=(cx - s, cy - s, s - g / 2, s - g / 2), width=lw)
        Line(rectangle=(cx + g / 2, cy - s, s - g / 2, s - g / 2), width=lw)

    def _draw_wallet(self):
        cx, cy, r = self._box(0.15)
        lw = self.line_width
        Line(rounded_rectangle=(cx - r, cy - r * 0.7, r * 2, r * 1.4, r * 0.18), width=lw)
        Line(points=[cx - r, cy + r * 0.3, cx + r, cy + r * 0.3], width=lw * 0.8)
        Ellipse(pos=(cx + r * 0.35, cy - r * 0.25), size=(r * 0.4, r * 0.4))

    def _draw_receipt(self):
        cx, cy, r = self._box(0.15)
        lw = self.line_width
        Line(points=[
            cx - r, cy + r, cx + r, cy + r, cx + r, cy - r * 0.7,
            cx + r * 0.6, cy - r, cx + r * 0.2, cy - r * 0.7,
            cx - r * 0.2, cy - r, cx - r * 0.6, cy - r * 0.7,
            cx - r, cy - r, cx - r, cy + r,
        ], width=lw, joint='round')
        Line(points=[cx - r * 0.55, cy + r * 0.45, cx + r * 0.55, cy + r * 0.45], width=lw * 0.7)
        Line(points=[cx - r * 0.55, cy + r * 0.05, cx + r * 0.55, cy + r * 0.05], width=lw * 0.7)
        Line(points=[cx - r * 0.55, cy - r * 0.35, cx + r * 0.2, cy - r * 0.35], width=lw * 0.7)

    def _draw_settings(self):
        cx, cy, r = self._box(0.12)
        lw = self.line_width
        Line(circle=(cx, cy, r * 0.45), width=lw)
        for i in range(8):
            ang = math.radians(i * 45)
            x1 = cx + math.cos(ang) * r * 0.62
            y1 = cy + math.sin(ang) * r * 0.62
            x2 = cx + math.cos(ang) * r * 0.98
            y2 = cy + math.sin(ang) * r * 0.98
            Line(points=[x1, y1, x2, y2], width=lw)

    def _draw_logout(self):
        cx, cy, r = self._box(0.15)
        lw = self.line_width
        Line(rounded_rectangle=(cx - r, cy - r, r * 0.9, r * 2, r * 0.12), width=lw)
        Line(points=[cx - r * 0.3, cy, cx + r, cy], width=lw, cap='round')
        Line(points=[cx + r * 0.45, cy + r * 0.5, cx + r, cy, cx + r * 0.45, cy - r * 0.5],
             width=lw, joint='round', cap='round')

    def _draw_category(self):
        cx, cy, r = self._box(0.2)
        lw = self.line_width
        Line(points=[cx - r, cy + r * 0.6, cx + r, cy + r * 0.6], width=lw, cap='round')
        Line(points=[cx - r, cy, cx + r, cy], width=lw, cap='round')
        Line(points=[cx - r, cy - r * 0.6, cx + r * 0.3, cy - r * 0.6], width=lw, cap='round')

    def _draw_user(self):
        cx, cy, r = self._box(0.18)
        lw = self.line_width
        Line(circle=(cx, cy + r * 0.35, r * 0.38), width=lw)
        Line(circle=(cx, cy - r * 0.9, r * 1.1, 20, 160), width=lw)

    def _draw_check(self):
        cx, cy, r = self._box(0.2)
        lw = self.line_width * 1.3
        Line(points=[cx - r, cy, cx - r * 0.2, cy - r * 0.8, cx + r, cy + r * 0.7],
             width=lw, joint='round', cap='round')

    def _draw_lock(self):
        cx, cy, r = self._box(0.2)
        lw = self.line_width
        Line(rounded_rectangle=(cx - r * 0.8, cy - r * 0.8, r * 1.6, r * 1.1, r * 0.15), width=lw)
        Line(circle=(cx, cy + r * 0.15, r * 0.55, 20, 160), width=lw)
        Ellipse(pos=(cx - r * 0.12, cy - r * 0.4), size=(r * 0.24, r * 0.24))

    def _draw_search(self):
        cx, cy, r = self._box(0.22)
        lw = self.line_width
        Line(circle=(cx - r * 0.15, cy + r * 0.15, r * 0.55), width=lw)
        Line(points=[cx + r * 0.35, cy - r * 0.35, cx + r * 0.85, cy - r * 0.85], width=lw * 1.2, cap='round')

class MenuButton(ButtonBehavior, BoxLayout):
    text = StringProperty("")
    icon_type = StringProperty("default")
    action_code = StringProperty("")
    callback = ObjectProperty(None)

def make_icon_label_button(text, icon_name, bg_color, on_release, icon_color=None,
                            icon_size=16, font_size=14, spacing=6, box_width=None, **kwargs):
    """Builds a RoundedButton with a centered icon+label combo (for buttons created in
    Python rather than declared in the .kv file, e.g. dynamically generated list rows)."""
    if icon_color is None:
        icon_color = Theme.TEXT_WHITE
    btn = RoundedButton(text='', bg_color=bg_color, **kwargs)
    box = BoxLayout(orientation='horizontal', size_hint=(None, None),
                     height=dp(icon_size + 4), spacing=dp(spacing))
    icon = IconWidget(size_hint=(None, None), size=(dp(icon_size), dp(icon_size)),
                       icon_name=icon_name, icon_color=icon_color)
    lbl = Label(text=text, color=icon_color, bold=True, font_size=sp(font_size),
                halign='left', valign='middle', size_hint=(None, None),
                height=dp(icon_size + 4))
    lbl.bind(texture_size=lambda inst, val: setattr(inst, 'size', (val[0], inst.height)))
    lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
    box.add_widget(icon)
    box.add_widget(lbl)

    def _fit_box(*_a):
        box.width = dp(icon_size) + dp(spacing) + lbl.width
        box.center = btn.center
    lbl.bind(width=_fit_box)
    btn.bind(pos=_fit_box, size=_fit_box)
    Clock.schedule_once(_fit_box, 0)

    btn.add_widget(box)
    btn.bind(on_release=on_release)
    return btn

class ProductCard(ButtonBehavior, BoxLayout):
    name = StringProperty("")
    price = StringProperty("0")
    stock = StringProperty("0")
    is_out = BooleanProperty(False)
    on_release_callback = ObjectProperty(None)

    def on_release(self):
        if self.is_out:
            return
        if self.on_release_callback:
            self.on_release_callback()

class CartItem(BoxLayout):
    name = StringProperty("")
    details = StringProperty("")
    total = StringProperty("")
    status = StringProperty("")
    item_id = StringProperty("")
    remove_callback = ObjectProperty(None)

class SessionButton(ButtonBehavior, BoxLayout):
    text_label = StringProperty("")
    total = StringProperty("")
    delete_callback = ObjectProperty(None)

class AdminProductItem(BoxLayout):
    name = StringProperty("")
    details = StringProperty("")
    cat = StringProperty("")
    prod_id = StringProperty("")
    edit_cb = ObjectProperty(None)
    delete_cb = ObjectProperty(None)

class AdminUserItem(BoxLayout):
    username = StringProperty("")
    role = StringProperty("")
    delete_cb = ObjectProperty(None)

class CategoryItem(BoxLayout):
    name = StringProperty("")
    cat_id = StringProperty("")
    edit_cb = ObjectProperty(None)
    delete_cb = ObjectProperty(None)

# --- COMBO BOX ---

class ComboSpinner(BoxLayout):
    text = StringProperty('')
    categories = ListProperty([])
    selected_id = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(50)

        self.main_btn = Button(
            text='Selecione Categoria',
            halign='left', valign='middle',
            background_color=Theme.BG_INPUT,
            color=Theme.TEXT_WHITE, size_hint_y=1, font_size=sp(16)
        )
        self.main_btn.bind(on_release=self.toggle_dropdown)
        self.arrow_btn = Button(
            text='', size_hint=(None, 1), width=dp(40),
            background_color=Theme.BG_INPUT
        )
        self.arrow_btn.bind(on_release=self.toggle_dropdown)
        self.arrow_icon = IconWidget(
            size_hint=(None, None), size=(dp(14), dp(14)),
            icon_name='chevron-down', icon_color=Theme.TEXT_GRAY
        )
        self.arrow_icon.center = self.arrow_btn.center
        self.arrow_btn.bind(center=lambda inst, val: setattr(self.arrow_icon, 'center', val))
        self.arrow_btn.add_widget(self.arrow_icon)

        btn_box = BoxLayout(orientation='horizontal', size_hint_y=1)
        btn_box.add_widget(self.main_btn)
        btn_box.add_widget(self.arrow_btn)
        self.add_widget(btn_box)

        self._dropdown = None
        self.bind(categories=self.on_categories)

    def on_categories(self, instance, value):
        if self._dropdown and self._dropdown.parent:
            self.refresh_dropdown()

    def toggle_dropdown(self, instance=None):
        if self._dropdown and self._dropdown.parent:
            self.close_dropdown()
            return
        self.open_dropdown()

    def open_dropdown(self):
        if not self._dropdown:
            self._dropdown = DropDown(auto_dismiss=True)
            self._dropdown.background_color = Theme.BG_CARD
            self._dropdown.bind(on_dismiss=self._on_dropdown_dismiss)
        self.refresh_dropdown()
        self._dropdown.open(self.main_btn)

    def close_dropdown(self):
        if self._dropdown:
            self._dropdown.dismiss()

    def refresh_dropdown(self):
        if not self._dropdown:
            return
        self._dropdown.clear_widgets()
        search_input = TextInput(
            hint_text='Buscar...', multiline=False, size_hint_y=None, height=dp(45),
            padding=[dp(10), dp(10)], background_color=Theme.BG_INPUT,
            foreground_color=Theme.TEXT_WHITE, hint_text_color=Theme.TEXT_GRAY,
            cursor_color=Theme.PRIMARY
        )
        self._dropdown.add_widget(search_input)
        scroll = ScrollView(size_hint_y=None, height=dp(200))
        layout = BoxLayout(orientation='vertical', size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        def filter_items(*args):
            term = search_input.text.lower()
            layout.clear_widgets()
            filtered = [c for c in self.categories if term in c['name'].lower()]
            if not filtered:
                layout.add_widget(Label(text='Nenhuma categoria', size_hint_y=None, height=dp(40), color=Theme.TEXT_GRAY))
            else:
                for cat in filtered:
                    btn = Button(text=cat['name'], size_hint_y=None, height=dp(44),
                                 background_color=Theme.BG_INPUT, color=Theme.TEXT_WHITE,
                                 halign='left', valign='middle', padding=[dp(10), 0])
                    btn.bind(on_release=lambda x, c=cat: self.select(c))
                    layout.add_widget(btn)
        search_input.bind(text=filter_items)
        filter_items()
        scroll.add_widget(layout)
        self._dropdown.add_widget(scroll)

    def _on_dropdown_dismiss(self, instance):
        pass

    def select(self, category):
        self.text = category['name']
        self.selected_id = category['id']
        self.main_btn.text = category['name']
        if self._dropdown:
            self._dropdown.dismiss()

# --- Loading Popup ---

class LoadingPopup(ModalView):
    auto_dismiss = False
    message = StringProperty("A processar...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.6, None)
        self.height = dp(120)
        self.background_color = [0, 0, 0, 0.5]
        self.background = ""

        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        with box.canvas.before:
            Color(*Theme.BG_CARD)
            RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(16),])
        box.bind(pos=self._update_rect, size=self._update_rect)

        self.msg_label = Label(text=self.message, color=Theme.TEXT_WHITE, font_size=sp(16))
        box.add_widget(self.msg_label)

        self.progress = ProgressBar(max=0)  # indeterminate
        self.progress.color = Theme.PRIMARY
        box.add_widget(self.progress)

        self.add_widget(box)

    def _update_rect(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(*Theme.BG_CARD)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(16),])

    def show(self, message="A processar..."):
        self.msg_label.text = message
        if not self.parent:
            self.open()

    def hide(self):
        if self.parent:
            self.dismiss()

# --- MODALS (all auto_dismiss=False) ---

class SideMenu(ModalView):
    auto_dismiss = False
    def __init__(self, callback, is_admin, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.size_hint = (None, 1)
        self.width = dp(280)
        self.pos_hint = {'right': 1, 'y': 0}
        self.background_color = [0, 0, 0, 0.6]
        self.background = ""
        menu_box = self.ids.menu_box
        if is_admin:
            self.add_menu_item(menu_box, "Relatórios", "reports", "reports")
            self.add_menu_item(menu_box, "Gestão de Usuários", "users", "users")
            self.add_menu_item(menu_box, "Estoque", "inventory", "inventory")
        self.add_menu_item(menu_box, "Sair", "logout", "logout")

    def add_menu_item(self, layout, text, icon_type, code):
        btn = MenuButton()
        btn.text = text
        btn.icon_type = icon_type
        btn.action_code = code
        btn.callback = self.on_item_click
        layout.add_widget(btn)

    def on_item_click(self, action_code):
        self.dismiss()
        self.callback(action_code)

class InfoPopup(ModalView):
    auto_dismiss = False
    message = StringProperty("")

class QtyPopup(ModalView):
    auto_dismiss = False
    qty = NumericProperty(1)
    product = ObjectProperty(None, allownone=True)
    product_name = StringProperty("")
    stock_label = StringProperty("")
    callback = ObjectProperty()

    def open_for(self, product, cb):
        self.product = product
        self.product_name = product['name']
        self.stock_label = f"Disponível: {product['stock']}"
        self.qty = 1
        self.callback = cb
        self.open()

    def adjust(self, val):
        new_qty = self.qty + val
        if self.product:
            if 1 <= new_qty <= self.product['stock']:
                self.qty = new_qty

    def confirm(self):
        if self.callback and self.product:
            self.callback(self.product, self.qty)
        self.dismiss()

class CartModal(ModalView):
    auto_dismiss = False
    cart_items = ListProperty([])
    total = NumericProperty(0)
    table_name = StringProperty("")
    has_pending = BooleanProperty(False)
    has_credit = BooleanProperty(False)
    table_credit = NumericProperty(0)
    payment_button_text = StringProperty("PAGAR CONTA")

    remove_callback = ObjectProperty()
    checkout_callback = ObjectProperty()
    confirm_callback = ObjectProperty()
    debt_callback = ObjectProperty()

    def update_data(self, cart, total, table, has_pending, table_credit=0):
        self.cart_items = cart
        self.total = total
        self.table_name = f"Mesa: {table}" if table else "Selecione uma mesa"
        self.has_pending = has_pending
        self.table_credit = table_credit
        self.ids.cart_list.clear_widgets()
        if not cart:
            self.ids.cart_list.add_widget(Label(text="Carrinho vazio", color=Theme.TEXT_GRAY, size_hint_y=None, height=dp(50)))
            return
        for i in cart:
            w = CartItem()
            w.name = i['name']
            time_str = i.get('timestamp', '')
            if 'tier_quantity' in i and 'pack_count' in i:
                w.details = f"{i['pack_count']} x Pack {i['tier_quantity']} un"
            elif 'tier_quantity' in i:
                w.details = f"Pack {i['tier_quantity']} un"
            else:
                w.details = f"{i['quantity']} x {i['unit_price']}"
            if time_str:
                w.details += f"  •  {time_str}"
            w.total = str(int(i.get('total_price', i['unit_price'] * i['quantity'])))
            w.status = i.get('status', 'pending')
            w.item_id = i['id']
            w.remove_callback = self.remove_callback
            self.ids.cart_list.add_widget(w)

class CategoryMgmtModal(ModalView):
    auto_dismiss = False
    editing_cat_id = StringProperty("")
    editing_cat_name = StringProperty("")

    def on_open(self):
        self.refresh()
        self.editing_cat_id = ""
        self.ids.add_btn.text = "Adicionar"
        self.ids.new_cat_input.text = ""

    def refresh(self):
        self.ids.cat_list.clear_widgets()
        for c in db.get_categories():
            w = CategoryItem()
            w.name = c['name']; w.cat_id = c['id']
            w.edit_cb = self.edit_cat; w.delete_cb = self.delete_cat
            self.ids.cat_list.add_widget(w)

    def add_cat(self, name):
        if not name: return
        if self.editing_cat_id:
            for cat in db.data['categories']:
                if cat['id'] == self.editing_cat_id: cat['name'] = name; break
            db._save_data(); self.editing_cat_id = ""; self.ids.add_btn.text = "Adicionar"
        else: db.add_category(name)
        self.ids.new_cat_input.text = ""; self.refresh()

    def edit_cat(self, cat_id, name):
        self.editing_cat_id = cat_id; self.ids.new_cat_input.text = name; self.ids.add_btn.text = "Salvar"

    def cancel_edit(self):
        self.editing_cat_id = ""; self.ids.new_cat_input.text = ""; self.ids.add_btn.text = "Adicionar"

    def delete_cat(self, cat_id):
        if any(p['categoryId'] == cat_id for p in db.get_products()):
            info = InfoPopup(); info.message = "Impossível excluir: existem produtos associados a esta categoria."; info.open()
            return
        db.data['categories'] = [c for c in db.data['categories'] if c['id'] != cat_id]
        db._save_data(); self.refresh()

class UserManagementModal(ModalView):
    auto_dismiss = False
    save_callback = ObjectProperty()
    def save(self, username, password, confirm):
        if not username or not password: self.ids.error_label.text = "Preencha todos os campos"; return
        if password != confirm: self.ids.error_label.text = "As senhas não coincidem"; return
        self.ids.error_label.text = ""; self.save_callback(username, password); self.dismiss()

class ProductModal(ModalView):
    auto_dismiss = False
    product_id = StringProperty("")
    name_txt = StringProperty("")
    price_txt = StringProperty("")
    stock_txt = StringProperty("")
    category_id = StringProperty("")
    categories = ListProperty([])
    price_tiers = ListProperty([])
    new_tier_qty = StringProperty("")
    new_tier_price = StringProperty("")
    save_callback = ObjectProperty()

    def setup(self, product=None):
        self.categories = db.get_categories()
        if 'cat_spinner' in self.ids: self.ids.cat_spinner.categories = self.categories
        if not self.category_id and self.categories: self.category_id = self.categories[0]['id']
        if product:
            self.product_id = product['id']; self.name_txt = product['name']; self.price_txt = str(product['price'])
            self.stock_txt = str(product['stock']); self.category_id = product['categoryId']
            self.price_tiers = product.get('priceTiers', [])[:]
            cat_name = next((c['name'] for c in self.categories if c['id'] == self.category_id), 'Selecione')
            if 'cat_spinner' in self.ids:
                self.ids.cat_spinner.text = cat_name; self.ids.cat_spinner.selected_id = self.category_id
                self.ids.cat_spinner.main_btn.text = cat_name
        else:
            self.product_id = ""; self.name_txt = ""; self.price_txt = ""; self.stock_txt = ""; self.price_tiers = []
            if 'cat_spinner' in self.ids and self.categories:
                self.category_id = self.categories[0]['id']; self.ids.cat_spinner.text = self.categories[0]['name']
                self.ids.cat_spinner.selected_id = self.categories[0]['id']; self.ids.cat_spinner.main_btn.text = self.categories[0]['name']
        self.refresh_tiers_list()

    def add_tier(self):
        try:
            qty = int(self.new_tier_qty); price = float(self.new_tier_price)
            if qty > 1 and price > 0:
                existing = next((t for t in self.price_tiers if t['quantity'] == qty), None)
                if existing: existing['totalPrice'] = price
                else: self.price_tiers.append({'quantity': qty, 'totalPrice': price})
                self.new_tier_qty = ""; self.new_tier_price = ""; self.refresh_tiers_list()
        except ValueError: pass

    def remove_tier(self, index):
        if 0 <= index < len(self.price_tiers): self.price_tiers.pop(index); self.refresh_tiers_list()

    def refresh_tiers_list(self):
        if 'tiers_list' not in self.ids: return
        self.ids.tiers_list.clear_widgets()
        for i, tier in enumerate(self.price_tiers):
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
            row.add_widget(Label(text=f"{tier['quantity']} un → Kz {tier['totalPrice']:.0f}", color=Theme.TEXT_WHITE, font_size=sp(14)))
            del_btn = IconButton(size_hint=(None, None), size=(dp(30), dp(30)), bg_color=Theme.DANGER, shadow_color=[0,0,0,0.5], shadow_offset=[dp(1), dp(1)])
            tier_icon = IconWidget(size_hint=(None, None), size=(dp(13), dp(13)), icon_name='trash', icon_color=Theme.TEXT_WHITE)
            tier_icon.center = del_btn.center
            del_btn.bind(center=lambda inst, val, ic=tier_icon: setattr(ic, 'center', val))
            del_btn.add_widget(tier_icon)
            del_btn.bind(on_release=lambda x, idx=i: self.remove_tier(idx))
            row.add_widget(del_btn)
            self.ids.tiers_list.add_widget(row)

    def save(self):
        if 'cat_spinner' in self.ids: self.category_id = self.ids.cat_spinner.selected_id
        if self.name_txt and self.price_txt:
            try:
                data = {'name': self.name_txt, 'price': float(self.price_txt), 'stock': int(self.stock_txt or '0'), 'categoryId': self.category_id, 'priceTiers': self.price_tiers}
                if self.product_id: data['id'] = self.product_id
                self.save_callback(data); self.dismiss()
            except ValueError: pass

class PrepaidPopup(ModalView):
    auto_dismiss = False
    callback = ObjectProperty()
    current_credit = NumericProperty(0)

    def open_for(self, current_credit, cb):
        self.current_credit = current_credit
        self.callback = cb
        self.ids.credit_input.text = ""
        if current_credit > 0:
            self.ids.current_credit_label.text = f"Saldo atual: Kz {current_credit:.2f}"
        else:
            self.ids.current_credit_label.text = ""
        self.open()

    def confirm(self, amount_text):
        try:
            amount = float(amount_text)
            if amount > 0:
                self.callback(amount)
                self.dismiss()
        except ValueError:
            pass

class DebtsPopup(ModalView):
    auto_dismiss = False
    pay_callback = ObjectProperty()
    delete_callback = ObjectProperty()

    def load(self, debts):
        self.ids.debt_list.clear_widgets()
        for d in debts:
            total = d['totalAmount']
            items = d.get('items', [])
            items_text = ""
            for it in items:
                items_text += f"• {it['quantity']}x {it['name']}\n"

            card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=dp(50 + 22*len(items) + 60),
                padding=dp(12),
                spacing=dp(6)
            )
            with card.canvas.before:
                Color(*Theme.BG_CARD)
                self._card_rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(12),])
            card.bind(pos=self._update_card_rect, size=self._update_card_rect)

            header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
            header.add_widget(Label(text=f"Mesa: {d['tableName']}", bold=True, font_size=sp(16), color=Theme.TEXT_WHITE))
            header.add_widget(Label(text=f"Kz {total:.2f}", halign='right', font_size=sp(16), color=Theme.SUCCESS))
            card.add_widget(header)

            lbl_items = Label(
                text=items_text.rstrip(),
                font_size=sp(14),
                color=Theme.TEXT_GRAY,
                halign='left',
                valign='top',
                size_hint_y=None,
                height=dp(20*len(items) + 10)
            )
            lbl_items.bind(width=lambda instance, value: setattr(instance, 'text_size', (value, None)))
            card.add_widget(lbl_items)

            actions = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(12))
            pay_btn = make_icon_label_button('Pagar', 'wallet', Theme.PRIMARY,
                                              lambda x, did=d['id']: self.pay_callback(did))
            actions.add_widget(pay_btn)

            del_btn = make_icon_label_button('Excluir', 'trash', Theme.DANGER,
                                              lambda x, did=d['id']: self.confirm_delete(did))
            actions.add_widget(del_btn)
            card.add_widget(actions)

            self.ids.debt_list.add_widget(card)

    def _update_card_rect(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(*Theme.BG_CARD)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(12),])

    def pay_debt(self, debt_id):
        self.dismiss()
        if self.pay_callback:
            self.pay_callback(debt_id)

    def confirm_delete(self, debt_id):
        auth = AuthPopup()
        auth.title_txt = "Excluir Dívida"
        auth.callback = lambda: self._do_delete(debt_id)
        auth.open()

    def _do_delete(self, debt_id):
        if self.delete_callback:
            self.delete_callback(debt_id)
        self.load(db.get_debts())

class ChangeConfirmationPopup(ModalView):
    auto_dismiss = False
    change_amount = NumericProperty(0)
    callback = ObjectProperty()

    def open_for(self, change, cb):
        self.change_amount = change
        self.callback = cb
        self.ids.change_label.text = f"Troco: Kz {change:.2f}" if change > 0 else "Sem troco"
        self.ids.pwd_input.text = ""
        self.ids.error_label.text = ""
        self.open()

    def verify_password(self, pwd):
        user = App.get_running_app().current_user
        if user and user['password'] == pwd:
            self.callback()
            self.dismiss()
        else:
            self.ids.error_label.text = "Senha Incorreta"

class AuthPopup(ModalView):
    auto_dismiss = False
    title_txt = StringProperty("Autorização")
    callback = ObjectProperty()
    def check(self, pwd):
        user = App.get_running_app().current_user
        if user and user['password'] == pwd: self.callback(); self.dismiss()
        else: self.ids.error_lbl.text = "Senha Incorreta"

class CheckoutPopup(ModalView):
    auto_dismiss = False
    total = NumericProperty()
    callback = ObjectProperty()
    def open_for(self, total, cb): self.total = total; self.callback = cb; self.ids.paid_input.text = ""; self.ids.change_label.text = "Troco: Kz 0.00"; self.open()
    def calc_change(self, val):
        try:
            paid = float(val) if val else 0; change = paid - self.total
            self.ids.change_label.text = f"Troco: Kz {max(0, change):.2f}"
            self.ids.change_label.color = Theme.SUCCESS if change >= 0 else Theme.DANGER
        except ValueError: pass
    def finalize(self, val):
        try:
            if float(val) >= self.total: self.callback(float(val)); self.dismiss()
        except ValueError: pass

class SessionsPopup(ModalView):
    auto_dismiss = False
    callback = ObjectProperty()
    delete_callback = ObjectProperty()

    def load(self, sessions):
        self.ids.sessions_grid.clear_widgets()
        for s in sessions:
            total = 0
            for i in s['orders']:
                if 'total_price' in i:
                    total += i['total_price']
                elif 'unit_price' in i:
                    total += i['unit_price'] * i['quantity']
                elif 'price' in i:
                    total += i['price'] * i['quantity']
            btn = SessionButton()
            btn.text_label = s['tableName']
            btn.total = f"Kz {total:.2f}"
            btn.bind(on_release=lambda x, t=s['tableName']: self.select(t))
            btn.delete_callback = lambda table=s['tableName']: self.confirm_delete(table)
            self.ids.sessions_grid.add_widget(btn)

    def select(self, table): self.callback(table); self.dismiss()
    def confirm_delete(self, table_name):
        auth = AuthPopup(); auth.title_txt = "Excluir Mesa"; auth.callback = lambda: self._do_delete(table_name); auth.open()
    def _do_delete(self, table_name):
        if self.delete_callback:
            self.delete_callback(table_name)

class TransactionsDetailsModal(ModalView):
    auto_dismiss = False
    def update_data(self, trans):
        layout = self.ids.trans_list; layout.clear_widgets(); layout.spacing = dp(5)
        for t in trans:
            try: dt = datetime.fromisoformat(t['timestamp']); formatted_date = dt.strftime('%d/%m/%Y %H:%M')
            except: formatted_date = t['timestamp']
            items = t.get('items', [])
            extra_lines = 0
            if 'paid' in t: extra_lines += 1
            if 'change' in t: extra_lines += 1
            box_height = dp(75 + 22*len(items) + 20*extra_lines)
            box = BoxLayout(orientation='vertical', size_hint_y=None, height=box_height, padding=dp(8), spacing=dp(2))
            with box.canvas.before:
                Color(*Theme.BG_CARD)
                RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(8),])
            box.bind(pos=self._update_rect, size=self._update_rect)
            box.add_widget(Label(text=f"Data: {formatted_date}", size_hint_y=None, height=dp(20), font_size=sp(14), bold=True))
            box.add_widget(Label(text=f"Mesa: {t['tableName']}", size_hint_y=None, height=dp(20), font_size=sp(14)))
            box.add_widget(Label(text=f"Total: Kz {t['totalAmount']:.2f}", size_hint_y=None, height=dp(20), font_size=sp(14), color=Theme.SUCCESS))
            for o in items:
                price = o.get('price', o.get('unit_price', 0))
                line = f"{o['quantity']}x {o['name']}  (Kz {price})  =  Kz {price * o['quantity']}"
                item_lbl = Label(text=line, size_hint_y=None, height=dp(20), color=(0.8,0.8,0.8,1), font_size=sp(12))
                box.add_widget(item_lbl)
            if 'paid' in t:
                box.add_widget(Label(text=f"Pago: Kz {t['paid']:.2f}", size_hint_y=None, height=dp(20), font_size=sp(14), color=(0.6,0.8,1,1)))
            if 'change' in t:
                box.add_widget(Label(text=f"Troco: Kz {t['change']:.2f}", size_hint_y=None, height=dp(20), font_size=sp(14), color=(1,0.8,0.6,1)))
            layout.add_widget(box)
    def _update_rect(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(*Theme.BG_CARD)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(8),])

# --- SCREENS ---

class LicenseScreen(Screen):
    machine_id = StringProperty('')
    def on_enter(self): self.machine_id = db.get_machine_id(); Clock.schedule_once(self.check_license)
    def check_license(self, dt):
        if db.get_license_key(): self.manager.current = 'login'
    def activate(self, key):
        if len(key) > 5: db.set_license_key(key); self.manager.current = 'login'
        else: self.ids.error_label.text = "Chave Inválida"

class LoginScreen(Screen):
    def do_login(self, username, password):
        user = db.authenticate(username, password)
        if user:
            App.get_running_app().current_user = user
            self.manager.get_screen('pos').is_admin = (user['role'] == 'admin')
            self.manager.get_screen('admin').current_user_role = user['role']
            self.manager.current = 'pos'
            self.ids.user_input.text = ""; self.ids.pass_input.text = ""; self.ids.error_label.text = ""
        else: self.ids.error_label.text = "Credenciais Inválidas"

class POSScreen(Screen):
    current_table = StringProperty('')
    current_user_name = StringProperty('')
    is_admin = BooleanProperty(False)
    cart = ListProperty([])
    cart_total = NumericProperty(0)
    has_pending = BooleanProperty(False)
    table_credit = NumericProperty(0)
    products = []; categories = []
    current_category = StringProperty(None, allownone=True)
    cart_modal = ObjectProperty(None); qty_modal = ObjectProperty(None); checkout_modal = ObjectProperty(None)
    sessions_modal = ObjectProperty(None); info_popup = ObjectProperty(None); side_menu = ObjectProperty(None)
    prepaid_popup = ObjectProperty(None)
    debts_popup = ObjectProperty(None)
    change_popup = ObjectProperty(None)
    loading_popup = ObjectProperty(None)

    def on_enter(self):
        user = App.get_running_app().current_user
        if user:
            self.current_user_name = user['username'].upper(); self.is_admin = (user['role'] == 'admin')
        self.loading_popup = LoadingPopup()
        self.load_data(); self.ids.rv_products.bind(width=self._update_cols)
        self.qty_modal = QtyPopup(); self.checkout_modal = CheckoutPopup(); self.cart_modal = CartModal()
        self.cart_modal.remove_callback = self.prompt_remove_item
        self.cart_modal.checkout_callback = self.prompt_checkout
        self.cart_modal.debt_callback = self.prompt_register_debt
        self.sessions_modal = SessionsPopup(); self.sessions_modal.callback = self.set_table; self.sessions_modal.delete_callback = self.delete_table_session
        self.info_popup = InfoPopup()
        self.prepaid_popup = PrepaidPopup()
        self.debts_popup = DebtsPopup()
        self.debts_popup.pay_callback = self.pay_debt
        self.debts_popup.delete_callback = self.remove_debt
        self.change_popup = ChangeConfirmationPopup()

    def show_loading(self, message="A processar..."):
        self.loading_popup.show(message)

    def hide_loading(self, dt=None):
        self.loading_popup.hide()

    def open_sessions(self):
        all_sessions = db.get_sessions()
        if not self.is_admin:
            user = App.get_running_app().current_user
            all_sessions = [s for s in all_sessions if s.get('userId') == user['username']]
        self.sessions_modal.load(all_sessions)
        self.sessions_modal.open()

    def open_prepaid_popup(self):
        if not self.current_table:
            self.info_popup.message = "Selecione uma mesa primeiro."
            self.info_popup.open()
            return
        self.prepaid_popup.open_for(self.table_credit, self.set_table_credit)

    def open_debts(self):
        all_debts = db.get_debts()
        if not self.is_admin:
            user = App.get_running_app().current_user
            all_debts = [d for d in all_debts if d.get('userId') == user['username']]
        self.debts_popup.load(all_debts)
        self.debts_popup.open()

    def set_table(self, name):
        self.current_table = name
        session = db.get_sessions()
        found = False
        user = App.get_running_app().current_user
        for s in session:
            if s['tableName'] == name:
                if self.is_admin or s.get('userId') == user['username']:
                    self.cart = s.get('orders', [])
                    self.table_credit = s.get('credit', 0)
                    found = True
                else:
                    self.cart = []
                    self.table_credit = 0
                    self.info_popup.message = "Esta mesa pertence a outro funcionário."
                    self.info_popup.open()
                break
        if not found:
            self.cart = []
            self.table_credit = 0
        self.calc_totals()

    def set_table_credit(self, amount):
        self.table_credit += amount
        self.save_session()
        self.calc_totals()

    def pay_debt(self, debt_id):
        debts = db.get_debts()
        debt = next((d for d in debts if d['id'] == debt_id), None)
        if not debt:
            return
        user = App.get_running_app().current_user
        if not self.is_admin and debt.get('userId') != user['username']:
            self.info_popup.message = "Você não pode pagar esta dívida."
            self.info_popup.open()
            return
        credit = 0
        sessions = db.get_sessions()
        for s in sessions:
            if s['tableName'] == debt.get('tableName', ''):
                credit = s.get('credit', 0)
                break
        net_total = max(0, debt['totalAmount'] - credit)
        if net_total == 0:
            db.remove_debt(debt_id)
            for s in sessions:
                if s['tableName'] == debt.get('tableName', ''):
                    s['credit'] = 0
                    db.save_session(s)
                    break
            self.info_popup.message = "Dívida paga com crédito existente."
            self.info_popup.open()
            if self.debts_popup.parent:
                all_debts = db.get_debts()
                if not self.is_admin:
                    all_debts = [d for d in all_debts if d.get('userId') == user['username']]
                self.debts_popup.load(all_debts)
        else:
            self.checkout_modal.open_for(net_total, lambda paid: self.finalize_debt_payment(debt, paid, credit))

    def finalize_debt_payment(self, debt, paid, credit_used):
        user = App.get_running_app().current_user
        if not self.is_admin and debt.get('userId') != user['username']:
            self.info_popup.message = "Ação não autorizada."
            self.info_popup.open()
            return
        total_paid = credit_used + paid
        change = total_paid - debt['totalAmount']
        db.checkout(debt['tableName'], debt['totalAmount'], debt['items'], paid=total_paid, change=change)
        db.remove_debt(debt['id'])
        if credit_used > 0:
            sessions = db.get_sessions()
            for s in sessions:
                if s['tableName'] == debt.get('tableName', ''):
                    s['credit'] = 0
                    db.save_session(s)
                    break
        if self.debts_popup.parent:
            all_debts = db.get_debts()
            if not self.is_admin:
                all_debts = [d for d in all_debts if d.get('userId') == user['username']]
            self.debts_popup.load(all_debts)

    def prompt_checkout(self):
        if self.table_credit > 0:
            if self.cart_total >= self.table_credit:
                extra = self.cart_total - self.table_credit
                self.checkout_modal.open_for(extra, self.do_checkout_with_credit)
            else:
                change = self.table_credit - self.cart_total
                self.change_popup.open_for(change, self.give_change)
        else:
            p = AuthPopup(callback=lambda: self.checkout_modal.open_for(self.cart_total, self.do_checkout))
            p.title_txt = "Autorizar Fechamento"
            p.open()

    def do_checkout_with_credit(self, paid):
        credit_used = min(self.table_credit, self.cart_total)
        total_paid = self.table_credit + paid
        change = total_paid - self.cart_total
        db.checkout(self.current_table, self.cart_total, self.cart, paid=total_paid, change=change)
        self.cart = []
        self.current_table = ""
        self.table_credit = 0
        self.ids.table_input.text = ""
        self.calc_totals()
        self.refresh_products()
        self.cart_modal.dismiss()

    def give_change(self):
        total_paid = self.table_credit
        change = self.table_credit - self.cart_total
        db.checkout(self.current_table, self.cart_total, self.cart, paid=total_paid, change=change)
        self.cart = []
        self.current_table = ""
        self.table_credit = 0
        self.ids.table_input.text = ""
        self.calc_totals()
        self.refresh_products()
        self.cart_modal.dismiss()

    def do_checkout(self, paid):
        change = paid - self.cart_total
        db.checkout(self.current_table, self.cart_total, self.cart, paid=paid, change=change)
        self.cart = []
        self.current_table = ""
        self.table_credit = 0
        self.ids.table_input.text = ""
        self.calc_totals()
        self.refresh_products()
        self.cart_modal.dismiss()

    def prompt_register_debt(self):
        if not self.cart:
            self.info_popup.message = "O carrinho está vazio."
            self.info_popup.open()
            return
        p = AuthPopup(callback=self.register_debt)
        p.title_txt = "Confirmar Dívida"
        p.open()

    def register_debt(self):
        user = App.get_running_app().current_user
        debt_data = {
            'tableName': self.current_table,
            'totalAmount': self.cart_total,
            'items': [dict(i) for i in self.cart],
            'userId': user['username'] if user else ''
        }
        db.add_debt(debt_data)
        db.remove_session(self.current_table)
        self.cart = []
        self.current_table = ""
        self.table_credit = 0
        self.ids.table_input.text = ""
        self.calc_totals()
        self.refresh_products()
        self.cart_modal.dismiss()

    def remove_debt(self, debt_id):
        debts = db.get_debts()
        debt = next((d for d in debts if d['id'] == debt_id), None)
        if debt and (self.is_admin or debt.get('userId') == App.get_running_app().current_user['username']):
            db.remove_debt(debt_id)
            if self.debts_popup.parent:
                all_debts = db.get_debts()
                if not self.is_admin:
                    user = App.get_running_app().current_user
                    all_debts = [d for d in all_debts if d.get('userId') == user['username']]
                self.debts_popup.load(all_debts)
        else:
            self.info_popup.message = "Ação não autorizada."
            self.info_popup.open()

    def add_to_cart(self, product, qty):
        # product now is always fresh from DB
        if product['stock'] <= 0:
            self.info_popup.message = "Produto esgotado."
            self.info_popup.open()
            return
        existing = next((i for i in self.cart if i['productId'] == product['id'] and i.get('type') == 'unit'), None)
        current_qty = existing['quantity'] if existing else 0
        new_total = current_qty + qty
        if new_total > product['stock']:
            self.info_popup.message = "Estoque insuficiente para esta quantidade."
            self.info_popup.open()
            return

        if not db.update_stock(product['id'], -qty):
            self.info_popup.message = "Erro ao reservar stock."
            self.info_popup.open()
            return

        if existing:
            existing['quantity'] += qty
            existing['confirmed_qty'] = existing['quantity']
        else:
            existing = {
                'id': str(uuid4()),
                'productId': product['id'],
                'name': product['name'],
                'unit_price': product['price'],
                'quantity': qty,
                'type': 'unit',
                'status': 'confirmed',
                'confirmed_qty': qty,
                'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            self.cart.append(existing)

        total_qty = existing['quantity']
        tiers = product.get('priceTiers', [])
        existing.pop('tier_quantity', None)
        existing.pop('pack_count', None)

        exact_tier = next((t for t in tiers if t['quantity'] == total_qty), None)
        if exact_tier:
            existing['total_price'] = exact_tier['totalPrice']
            existing['tier_quantity'] = exact_tier['quantity']
            existing['pack_count'] = 1
        else:
            applicable = [t for t in tiers if total_qty % t['quantity'] == 0]
            if applicable:
                best = max(applicable, key=lambda t: t['quantity'])
                packs = total_qty // best['quantity']
                existing['total_price'] = packs * best['totalPrice']
                existing['tier_quantity'] = best['quantity']
                existing['pack_count'] = packs
            else:
                existing['total_price'] = product['price'] * total_qty

        self.products = db.get_products()
        self.save_session()
        self.calc_totals()
        self.refresh_products()

    def prompt_remove_item(self, widget_item):
        p = AuthPopup(callback=lambda: self.remove_item(widget_item.item_id))
        p.title_txt = "Confirmar Exclusão"
        p.open()

    def remove_item(self, item_id):
        target = next((i for i in self.cart if i['id'] == item_id), None)
        if target:
            db.update_stock(target['productId'], target['quantity'])
            self.cart.remove(target)
            self.products = db.get_products()
            self.save_session()
            self.calc_totals()
            self.refresh_products()

    def delete_table_session(self, table_name):
        user = App.get_running_app().current_user
        sessions = db.get_sessions()
        session = next((s for s in sessions if s['tableName'] == table_name), None)
        if session and (self.is_admin or session.get('userId') == user['username']):
            for item in session.get('orders', []):
                db.update_stock(item['productId'], item['quantity'])
            db.remove_session(table_name)
            if self.current_table == table_name:
                self.current_table = ""
                self.table_credit = 0
                self.ids.table_input.text = ""
                self.cart = []
                self.products = db.get_products()
                self.calc_totals()
                self.refresh_products()

            if self.sessions_modal.parent:
                all_sessions = db.get_sessions()
                if not self.is_admin:
                    all_sessions = [s for s in all_sessions if s.get('userId') == user['username']]
                self.sessions_modal.load(all_sessions)
        else:
            self.info_popup.message = "Você não tem permissão para excluir esta mesa."
            self.info_popup.open()

    def open_side_menu(self):
        if not self.side_menu: self.side_menu = SideMenu(callback=self.handle_menu_action, is_admin=self.is_admin)
        self.side_menu.open()
    def handle_menu_action(self, action):
        if action == 'logout': self.logout()
        elif action in ['reports', 'inventory', 'users']: self.go_admin_tab(action)
    def go_admin_tab(self, tab):
        self.manager.get_screen('admin').set_tab(tab); self.manager.current = 'admin'
    def _update_cols(self, instance, width): pass

    def load_data(self):
        self.show_loading("A carregar produtos...")
        threading.Thread(target=self._load_data_thread).start()
    def _load_data_thread(self):
        self.categories = db.get_categories(); self.products = db.get_products()
        Clock.schedule_once(lambda dt: self.refresh_categories())
        Clock.schedule_once(lambda dt: self.refresh_products())
        Clock.schedule_once(lambda dt: self.hide_loading(), 0)
    def refresh_categories(self):
        box = self.ids.category_box; box.clear_widgets()
        all_btn = CategoryButton(text="TODOS")
        if not self.current_category: all_btn.bg_color = Theme.PRIMARY; all_btn.text_color = Theme.TEXT_WHITE
        all_btn.bind(on_release=lambda x: self.filter_category(None)); box.add_widget(all_btn)
        for cat in self.categories:
            btn = CategoryButton(text=cat['name'].upper())
            if self.current_category == cat['id']: btn.bg_color = Theme.PRIMARY; btn.text_color = Theme.TEXT_WHITE
            btn.bind(on_release=lambda x, cid=cat['id']: self.filter_category(cid)); box.add_widget(btn)
    def filter_category(self, cat_id): self.current_category = cat_id; self.refresh_categories(); self.refresh_products()
    def refresh_products(self):
        filtered = [p for p in self.products if not self.current_category or p['categoryId'] == self.current_category]
        rv_data = [
            {
                'name': p['name'],
                'price': str(p['price']),
                'stock': str(p['stock']),
                'is_out': p['stock'] <= 0,
                'on_release_callback': lambda prod=p: self._on_product_tap(prod)
            } for p in filtered
        ]
        self.ids.rv_products.data = rv_data

    def _on_product_tap(self, product):
        # Re-fetch fresh product data from DB to ensure accurate stock
        fresh_product = next((p for p in db.get_products() if p['id'] == product['id']), None)
        if not fresh_product:
            return
        if fresh_product['stock'] <= 0:
            self.info_popup.message = "Sem stock"
            self.info_popup.open()
            return
        if not self.current_table:
            self.info_popup.message = "Por favor, selecione uma mesa primeiro!"
            self.info_popup.open()
            return
        self.qty_modal.open_for(fresh_product, self.add_to_cart)

    def open_qty(self, product):
        self._on_product_tap(product)

    def calc_totals(self):
        self.cart_total = sum(i.get('total_price', i['unit_price'] * i['quantity']) for i in self.cart)
        self.has_pending = False
        for i in self.cart:
            i['status'] = 'confirmed'
        if self.cart_modal.parent:
            self.cart_modal.update_data(self.cart, self.cart_total, self.current_table, self.has_pending, self.table_credit)

    def open_cart(self):
        self.cart_modal.has_credit = (self.table_credit > 0)
        self.cart_modal.table_credit = self.table_credit
        if self.table_credit > 0:
            diff = self.table_credit - self.cart_total
            if diff > 0:
                self.cart_modal.payment_button_text = "Dar Troco"
            elif diff == 0:
                self.cart_modal.payment_button_text = "Fechar Conta"
            else:
                self.cart_modal.payment_button_text = "Pagar Diferença"
        else:
            self.cart_modal.payment_button_text = "Pagar Conta"
        self.cart_modal.update_data(self.cart, self.cart_total, self.current_table, self.has_pending, self.table_credit)
        self.cart_modal.open()

    def save_session(self):
        if self.current_table:
            user = App.get_running_app().current_user
            db.save_session({
                'tableName': self.current_table,
                'orders': self.cart,
                'credit': self.table_credit,
                'userId': user['username'] if user else ''
            })

    def go_admin(self): self.manager.current = 'admin'
    def logout(self): self.manager.current = 'login'

class AdminScreen(Screen):
    current_tab = StringProperty('reports')
    current_user_role = StringProperty('admin')
    report_filter = StringProperty('daily')
    report_total = StringProperty("0")
    report_count = StringProperty("0")
    report_avg = StringProperty("0")
    report_filter_label = StringProperty("Dia")
    custom_start = StringProperty("")
    custom_end = StringProperty("")
    is_custom_visible = BooleanProperty(False)
    inv_search = StringProperty("")
    prod_modal = ObjectProperty(None); cat_modal = ObjectProperty(None); user_modal = ObjectProperty(None); trans_modal = ObjectProperty(None)
    filtered_transactions = []
    loading_popup = ObjectProperty(None)

    def on_enter(self):
        self.loading_popup = LoadingPopup()
        self.prod_modal = ProductModal(save_callback=self.save_product); self.cat_modal = CategoryMgmtModal()
        self.user_modal = UserManagementModal(save_callback=self.add_user); self.trans_modal = TransactionsDetailsModal()
        self.refresh_data(); self._init_filters(); Clock.schedule_once(self._fix_tabs_z_order, 0)

    def show_loading(self, message="A processar..."):
        self.loading_popup.show(message)

    def hide_loading(self, dt=None):
        self.loading_popup.hide()

    def _fix_tabs_z_order(self, dt):
        if 'tabs_box' in self.ids: self.ids.tabs_box.y = self.height - dp(120)

    def _init_filters(self):
        filters = [('daily', 'Dia'), ('weekly', 'Semana'), ('monthly', 'Mês'), ('annual', 'Ano'), ('general', 'Geral'), ('custom', 'Person.')]
        box = self.ids.filter_box; box.clear_widgets()
        for f_id, f_label in filters:
            btn = ReportFilterButton(text=f_label, group="rep_filters")
            if self.report_filter == f_id: btn.selected = True
            btn.bind(on_release=lambda x, fid=f_id, lbl=f_label: self.filter_report(fid, lbl)); box.add_widget(btn)

    def set_tab(self, tab_name): self.current_tab = tab_name; self.refresh_data()

    def filter_report(self, r_type, label):
        self.report_filter = r_type; self.report_filter_label = label; self.is_custom_visible = (r_type == 'custom')
        for child in self.ids.filter_box.children:
            if isinstance(child, ReportFilterButton): child.selected = (child.text == label)
        self.show_loading("A calcular relatórios...")
        threading.Thread(target=self._calc_reports_thread).start()

    def on_custom_date_change(self):
        if self.report_filter == 'custom':
            self.show_loading("A calcular relatórios...")
            threading.Thread(target=self._calc_reports_thread).start()

    def refresh_data(self):
        if self.current_tab == 'reports':
            self.show_loading("A calcular relatórios...")
            threading.Thread(target=self._calc_reports_thread).start()
        elif self.current_tab == 'inventory':
            self._load_inventory()
        elif self.current_tab == 'users':
            self._load_users()

    def _calc_reports_thread(self):
        trans = db.data.get('transactions', [])
        filtered = []
        now = datetime.now()
        if self.report_filter == 'daily':
            target = now.strftime('%Y-%m-%d')
            filtered = [t for t in trans if t['timestamp'].startswith(target)]
        elif self.report_filter == 'weekly':
            start_week = now - timedelta(days=now.weekday())
            filtered = [t for t in trans if t['timestamp'] >= start_week.strftime('%Y-%m-%d')]
        elif self.report_filter == 'monthly':
            target = now.strftime('%Y-%m')
            filtered = [t for t in trans if t['timestamp'].startswith(target)]
        elif self.report_filter == 'annual':
            target = now.strftime('%Y')
            filtered = [t for t in trans if t['timestamp'].startswith(target)]
        elif self.report_filter == 'custom':
            s = self.custom_start; e = self.custom_end
            filtered = trans
            if s: filtered = [t for t in filtered if t['timestamp'] >= s]
            if e: filtered = [t for t in filtered if t['timestamp'] <= e + "T23:59:59"]
        else: filtered = trans
        total = sum(t['totalAmount'] for t in filtered); count = len(filtered); avg = total / count if count else 0

        daily_revenue = {}
        for i in range(7):
            day = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_revenue[day] = 0
        for t in trans:
            day = t['timestamp'][:10]
            if day in daily_revenue:
                daily_revenue[day] += t['totalAmount']
        sorted_days = sorted(daily_revenue.keys())
        values = [daily_revenue[d] for d in sorted_days]
        max_val = max(values) if values and max(values) > 0 else 1

        def update_ui(dt):
            self.report_total = f"Kz {total:,.0f}"
            self.report_count = str(count)
            self.report_avg = f"Kz {avg:,.0f}"
            self.filtered_transactions = filtered
            if 'chart_box' in self.ids:
                chart = self.ids.chart_box
                chart.canvas.clear()
                with chart.canvas:
                    Color(*Theme.BG_CARD)
                    Rectangle(pos=chart.pos, size=chart.size)
                    bar_width = chart.width / 10
                    for i, day in enumerate(sorted_days):
                        val = values[i]
                        bar_height = (val / max_val) * (chart.height - dp(20))
                        x = chart.x + i * (bar_width + dp(5)) + dp(5)
                        y = chart.y + dp(10)
                        Color(*Theme.PRIMARY)
                        Rectangle(pos=(x, y), size=(bar_width, bar_height))
            self.hide_loading()
        Clock.schedule_once(update_ui)

    def show_transactions_details(self): self.trans_modal.update_data(self.filtered_transactions); self.trans_modal.open()

    def _load_inventory(self):
        self.show_loading("A carregar produtos...")
        threading.Thread(target=self._load_inventory_thread).start()
    def _load_inventory_thread(self):
        all_prods = db.get_products(); cats = db.get_categories(); cat_map = {c['id']: c['name'] for c in cats}
        term = self.inv_search.lower()
        rv_data = []
        for p in all_prods:
            if term in p['name'].lower():
                rv_data.append({
                    'name': p['name'], 'details': f"Kz {p['price']} | Est: {p['stock']}", 'cat': cat_map.get(p['categoryId'], ''),
                    'prod_id': p['id'], 'edit_cb': lambda x=p: self.prompt_edit_product(x), 'delete_cb': lambda i=p['id']: self.prompt_delete_product(i)
                })
        def update_ui(dt):
            self.ids.inventory_rv.data = rv_data
            self.hide_loading()
        Clock.schedule_once(update_ui)

    def _load_users(self):
        def update_ui(dt):
            users = db.data.get('users', [])
            rv_data = [{'username': u['username'], 'role': u['role'], 'delete_cb': lambda name=u['username']: self.delete_user(name)} for u in users]
            self.ids.users_rv.data = rv_data
        Clock.schedule_once(update_ui)

    def prompt_add_product(self):
        p = AuthPopup(callback=self.open_product_modal); p.title_txt = "Adicionar Produto"; p.open()
    def prompt_edit_product(self, product):
        def on_auth(): self.open_product_modal(product)
        p = AuthPopup(callback=on_auth); p.title_txt = "Editar Produto"; p.open()
    def prompt_delete_product(self, prod_id):
        for s in db.get_sessions():
            for order in s.get('orders', []):
                if order.get('productId') == prod_id:
                    info = InfoPopup(); info.message = "Impossível excluir o produto: ele está presente em uma mesa aberta."; info.open()
                    return
        p = AuthPopup(callback=lambda pid=prod_id: self.delete_product(pid)); p.title_txt = "Excluir Produto"; p.open()

    def open_product_modal(self, product=None): self.prod_modal.setup(product); self.prod_modal.open()
    def open_categories(self): self.cat_modal.open()
    def open_user_modal(self):
        self.user_modal.ids.new_user_name.text = ""; self.user_modal.ids.new_user_pass.text = ""; self.user_modal.ids.new_user_pass_confirm.text = ""; self.user_modal.open()

    def save_product(self, data):
        prods = db.get_products()
        if 'id' in data:
            for i, p in enumerate(prods):
                if p['id'] == data['id']: prods[i].update(data); break
        else:
            data['id'] = str(uuid4()); prods.append(data)
        db.data['products'] = prods; db._save_data(); self.refresh_data()

    def delete_product(self, prod_id):
        db.data['products'] = [p for p in db.get_products() if p['id'] != prod_id]; db._save_data(); self.refresh_data()

    def add_user(self, u, p):
        if u and p:
            db.data['users'].append({'username': u, 'password': p, 'role': 'employee'}); db._save_data(); self.refresh_data()

    def delete_user(self, username):
        if username == 'admin': return
        popup = AuthPopup(callback=lambda: self._do_delete_user(username)); popup.title_txt = "Excluir Usuário"; popup.open()
    def _do_delete_user(self, username):
        db.data['users'] = [u for u in db.data['users'] if u['username'] != username]; db._save_data(); self.refresh_data()

    def go_back(self): self.manager.current = 'pos'

class BarPOSApp(App):
    current_user = None
    def build(self):
        self.title = "BarPOS Moderno"
        Window.clearcolor = Theme.BG_MAIN
        Window.softinput_mode = 'below_target'
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(LicenseScreen(name='license'))
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(POSScreen(name='pos'))
        sm.add_widget(AdminScreen(name='admin'))
        return sm

if __name__ == '__main__':
    BarPOSApp().run()