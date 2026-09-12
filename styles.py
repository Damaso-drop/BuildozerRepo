from kivy.utils import get_color_from_hex

class Theme:
    BG_MAIN = get_color_from_hex('#0f172a')
    BG_CARD = get_color_from_hex('#1e293b')
    BG_INPUT = get_color_from_hex('#334155')

    PRIMARY = get_color_from_hex('#7c3aed')
    SECONDARY = get_color_from_hex('#0d9488')
    DANGER = get_color_from_hex('#e11d48')
    SUCCESS = get_color_from_hex('#059669')
    WARNING = get_color_from_hex('#f59e0b')

    TEXT_WHITE = get_color_from_hex('#f8fafc')
    TEXT_GRAY = get_color_from_hex('#94a3b8')
    TEXT_MUTED = get_color_from_hex('#64748b')

    # --- NEW ---
    STOCK_LOW_THRESHOLD = 5   # show ⚠ when stock <= this value