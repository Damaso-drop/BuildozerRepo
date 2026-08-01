from kivy.utils import get_color_from_hex

class Theme:
    # Tailwind Slate Palette
    BG_MAIN = get_color_from_hex('#0f172a')  # Slate 900
    BG_CARD = get_color_from_hex('#1e293b')  # Slate 800
    BG_INPUT = get_color_from_hex('#334155') # Slate 700
    
    # Accents
    PRIMARY = get_color_from_hex('#7c3aed')  # Violet 600
    SECONDARY = get_color_from_hex('#0d9488') # Teal 600
    DANGER = get_color_from_hex('#e11d48')   # Rose 600
    SUCCESS = get_color_from_hex('#059669')  # Emerald 600
    WARNING = get_color_from_hex('#f59e0b')  # Amber 500
    
    # Text
    TEXT_WHITE = get_color_from_hex('#f8fafc') # Slate 50
    TEXT_GRAY = get_color_from_hex('#94a3b8')  # Slate 400
    TEXT_MUTED = get_color_from_hex('#64748b') # Slate 500