"""
BarPOS License Manager — single-file module.

Handles:
  • Ed25519 keypair generation
  • License issuance (interactive menu or CLI flags)
  • License validation (Ed25519 v2, with legacy HMAC fallback)
  • Human-readable time-remaining formatting

Usage (CLI):
    python license_manager.py                # interactive menu
    python license_manager.py --gen-keys     # generate keypair
    python license_manager.py --issue        # issue a license
    python license_manager.py --validate     # validate a key
    python license_manager.py --help

Usage (Pydroid / IDE "Run" button):
    Just tap Run — you get the same menu, no arguments needed.

Usage (import from other modules):
    import license_manager
    key = license_manager.generate_license_key(machine_id, "2026-12-31")
"""
import hmac
import hashlib
import base64
import json
import os
import sys
import time
import re
from datetime import datetime, date, timedelta

# ---------------------------------------------------------------------------
# Legacy shared secret — ONLY used to validate old-format licenses that
# were already issued. New licenses use Ed25519 and do NOT depend on any
# secret stored in this file.
# ---------------------------------------------------------------------------
_LEGACY_SECRET = b"BarPOS_S3cr3t_Lic3ns3_K3y_2024"

# ---------------------------------------------------------------------------
# Ed25519 asymmetric signing (preferred).
# The app embeds ONLY the public key below. The matching private key
# lives exclusively on the developer's machine (license_private.pem)
# and must NEVER be committed or bundled into an APK.
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    _HAS_ED25519 = True
except ImportError:
    _HAS_ED25519 = False


# Replace this placeholder with YOUR public key (run the menu option 1
# once, then paste the printed PUBLIC KEY below). Until you do that, only
# legacy HMAC keys will validate.
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
-----END PUBLIC KEY-----"""

V2_PREFIX = "v2."

DEFAULT_PRIVATE_KEY_PATH = 'license_private.pem'
DEFAULT_PUBLIC_KEY_PATH = 'license_public.pem'


# ===========================================================================
# Key management
# ===========================================================================
def generate_keypair(private_key_path=DEFAULT_PRIVATE_KEY_PATH,
                     public_key_path=DEFAULT_PUBLIC_KEY_PATH):
    """Generate an Ed25519 keypair. Run once, keep the private file secret."""
    if not _HAS_ED25519:
        raise RuntimeError(
            "cryptography not installed. Install it with:\n"
            "    pip install cryptography")
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(private_key_path, 'wb') as f:
        f.write(priv_bytes)
    with open(public_key_path, 'wb') as f:
        f.write(pub_bytes)
    return priv_bytes, pub_bytes


def _load_private_key(path=DEFAULT_PRIVATE_KEY_PATH):
    if not _HAS_ED25519:
        raise RuntimeError("cryptography not installed")
    with open(path, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _load_public_key():
    if not _HAS_ED25519:
        return None
    try:
        return serialization.load_pem_public_key(PUBLIC_KEY_PEM)
    except Exception:
        return None


# ===========================================================================
# Legacy HMAC helpers (kept ONLY for old license keys)
# ===========================================================================
def _legacy_sign(payload_bytes):
    return hmac.new(_LEGACY_SECRET, payload_bytes, hashlib.sha256).digest()


def _b64encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def _b64decode(data):
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


# ===========================================================================
# Expiry parsing
# ===========================================================================
def _parse_expiry_input(expiry_input):
    now = datetime.now()
    match = re.fullmatch(r'(\d+)\s*([smhd])', expiry_input.strip().lower())
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        delta_map = {
            's': timedelta(seconds=value),
            'm': timedelta(minutes=value),
            'h': timedelta(hours=value),
            'd': timedelta(days=value),
        }
        return now + delta_map[unit]

    try:
        return datetime.strptime(expiry_input.strip(), '%Y-%m-%d %H:%M')
    except ValueError:
        pass

    try:
        d = datetime.strptime(expiry_input.strip(), '%Y-%m-%d')
        return d.replace(hour=23, minute=59, second=59)
    except ValueError:
        pass

    raise ValueError("Formato de expiração inválido")


# ===========================================================================
# License issuance
# ===========================================================================
def generate_license_key(machine_id, expiry_input,
                         private_key_path=DEFAULT_PRIVATE_KEY_PATH):
    """Generate a v2 (Ed25519) license if a private key is available;
    otherwise fall back to legacy HMAC (dev / offline)."""
    expiry_dt = _parse_expiry_input(expiry_input)
    payload = {
        "machine_id": machine_id,
        "expiry": expiry_dt.isoformat(),
        "issued": datetime.now().isoformat()
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')

    if _HAS_ED25519 and os.path.exists(private_key_path):
        try:
            priv = _load_private_key(private_key_path)
            sig = priv.sign(payload_json)
            return V2_PREFIX + _b64encode(payload_json) + "." + _b64encode(sig)
        except Exception as e:
            print(f"[license] Ed25519 signing failed ({e}); using legacy HMAC")

    sig = _legacy_sign(payload_json)
    return _b64encode(payload_json) + "." + _b64encode(sig)


# ===========================================================================
# License validation
# ===========================================================================
def _check_payload(payload, machine_id, current_datetime):
    if payload.get('machine_id') != machine_id:
        return False, "Chave não pertence a este dispositivo"
    expiry_str = payload.get('expiry')
    if not expiry_str:
        return False, "Data de expiração ausente"
    try:
        expiry_dt = datetime.fromisoformat(expiry_str)
    except ValueError:
        try:
            expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59)
        except ValueError:
            return False, "Data inválida"
    current = current_datetime or datetime.now()
    if current > expiry_dt:
        return False, "Licença expirada"
    return True, "Licença válida"


def _validate_v2(body, machine_id, current_datetime):
    if '.' not in body:
        return False, "Chave inválida"
    try:
        payload_b64, sig_b64 = body.split('.', 1)
        payload_json = _b64decode(payload_b64)
        signature = _b64decode(sig_b64)
        pub = _load_public_key()
        if pub is None:
            return False, "Chave pública ausente"
        try:
            pub.verify(signature, payload_json)
        except InvalidSignature:
            return False, "Assinatura inválida"
        payload = json.loads(payload_json.decode('utf-8'))
        return _check_payload(payload, machine_id, current_datetime)
    except Exception:
        return False, "Erro ao validar chave"


def _validate_legacy(body, machine_id, current_datetime):
    if '.' not in body:
        return False, "Chave inválida"
    try:
        payload_b64, sig_b64 = body.split('.', 1)
        payload_json = _b64decode(payload_b64)
        signature = _b64decode(sig_b64)
        expected = _legacy_sign(payload_json)
        if not hmac.compare_digest(signature, expected):
            return False, "Assinatura inválida"
        payload = json.loads(payload_json.decode('utf-8'))
        return _check_payload(payload, machine_id, current_datetime)
    except Exception:
        return False, "Erro ao validar chave"


def validate_license_key(key, machine_id, current_datetime=None):
    if not key:
        return False, "Chave inválida"
    if key.startswith(V2_PREFIX):
        return _validate_v2(key[len(V2_PREFIX):], machine_id, current_datetime)
    return _validate_legacy(key, machine_id, current_datetime)


def check_time_tampering(last_seen, current_time=None):
    if current_time is None:
        current_time = time.time()
    if last_seen is None:
        return False, current_time
    tolerance = 60
    if current_time < last_seen - tolerance:
        return True, last_seen
    return False, max(current_time, last_seen)


# ===========================================================================
# Time-remaining helpers
# ===========================================================================
def get_license_payload(key):
    if not key:
        return None
    try:
        if key.startswith(V2_PREFIX):
            body = key[len(V2_PREFIX):]
            if '.' not in body:
                return None
            payload_b64, sig_b64 = body.split('.', 1)
            payload_json = _b64decode(payload_b64)
            signature = _b64decode(sig_b64)
            pub = _load_public_key()
            if pub is None:
                return None
            try:
                pub.verify(signature, payload_json)
            except InvalidSignature:
                return None
            return json.loads(payload_json.decode('utf-8'))
        else:
            if '.' not in key:
                return None
            payload_b64, sig_b64 = key.split('.', 1)
            payload_json = _b64decode(payload_b64)
            signature = _b64decode(sig_b64)
            expected = _legacy_sign(payload_json)
            if not hmac.compare_digest(signature, expected):
                return None
            return json.loads(payload_json.decode('utf-8'))
    except Exception:
        return None


def format_remaining(delta):
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "Expirada"

    months = total_seconds // (30 * 86400)
    rem = total_seconds % (30 * 86400)
    days = rem // 86400
    rem %= 86400
    hours = rem // 3600
    rem %= 3600
    minutes = rem // 60

    def plural(n, singular, plural_form):
        return f"{n} {singular if n == 1 else plural_form}"

    parts = []
    if months > 0:
        parts.append(plural(months, "mês", "meses"))
        if days > 0:
            parts.append(plural(days, "dia", "dias"))
    elif days > 0:
        parts.append(plural(days, "dia", "dias"))
        if hours > 0:
            parts.append(plural(hours, "hora", "horas"))
    elif hours > 0:
        parts.append(plural(hours, "hora", "horas"))
        if minutes > 0:
            parts.append(plural(minutes, "minuto", "minutos"))
    else:
        if minutes > 0:
            parts.append(plural(minutes, "minuto", "minutos"))
        else:
            return "menos de 1 minuto"

    return " e ".join(parts)


def get_license_time_remaining(key, machine_id, current_datetime=None):
    payload = get_license_payload(key)
    if payload is None:
        return False, "Sem licença"
    if payload.get('machine_id') != machine_id:
        return False, "Dispositivo errado"
    expiry_str = payload.get('expiry')
    if not expiry_str:
        return False, "Sem expiração"
    try:
        expiry_dt = datetime.fromisoformat(expiry_str)
    except ValueError:
        try:
            expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59)
        except ValueError:
            return False, "Data inválida"
    current = current_datetime or datetime.now()
    if current > expiry_dt:
        return False, "Expirada"
    return True, format_remaining(expiry_dt - current)


# ===========================================================================
# CLI actions
# ===========================================================================
def _safe_input(prompt):
    """input() that returns None on EOF (Pydroid without stdin)."""
    try:
        return input(prompt)
    except EOFError:
        return None


def _cli_generate_keys():
    print("\n--- Gerar par de chaves Ed25519 ---\n")
    if not _HAS_ED25519:
        print("ERRO: A biblioteca 'cryptography' não está instalada.")
        print("Instale com:")
        print("    pip install cryptography")
        print("\nEnquanto isso, o sistema usará HMAC legado automaticamente.")
        return 1
    if os.path.exists(DEFAULT_PRIVATE_KEY_PATH):
        ans = _safe_input(
            f"'{DEFAULT_PRIVATE_KEY_PATH}' já existe. Sobrescrever? (s/N): ")
        if (ans or '').strip().lower() != 's':
            print("Cancelado.")
            return 0
    try:
        priv, pub = generate_keypair()
        cwd = os.path.abspath('.')
        print(f"\nOK — Chaves geradas em: {cwd}")
        print(f"  • {DEFAULT_PRIVATE_KEY_PATH}   (MANTENHA SECRETO)")
        print(f"  • {DEFAULT_PUBLIC_KEY_PATH}")
        print("\n--- COPIE O BLOCO ABAIXO PARA 'PUBLIC_KEY_PEM' EM license_manager.py ---\n")
        print(pub.decode())
        print("--- FIM ---\n")
        print("NUNCA envie license_private.pem no APK.")
        return 0
    except Exception as e:
        print(f"Erro: {e}")
        return 1


def _cli_issue_license():
    print("\n--- Gerar licença para um cliente ---\n")
    if _HAS_ED25519 and not os.path.exists(DEFAULT_PRIVATE_KEY_PATH):
        print(f"Aviso: '{DEFAULT_PRIVATE_KEY_PATH}' não encontrado.")
        print("A licença será gerada no formato LEGADO (HMAC).")
        print("Para usar Ed25519, rode a opção 1 do menu primeiro.\n")
    elif not _HAS_ED25519:
        print("Aviso: 'cryptography' não instalada.")
        print("A licença será gerada no formato LEGADO (HMAC).\n")

    machine_id = (_safe_input("Digite o ID da máquina: ") or '').strip()
    if not machine_id:
        print("Erro: ID da máquina é obrigatório.")
        return 1
    expiry_input = (_safe_input(
        "Digite a expiração (ex: 2026-12-31, 30d, 2h, 30m): ") or '').strip()
    if not expiry_input:
        print("Erro: expiração é obrigatória.")
        return 1
    try:
        key = generate_license_key(machine_id, expiry_input)
    except ValueError as e:
        print(f"Erro: {e}")
        return 1
    print("\nChave de licença gerada:\n")
    print(key)
    print("\nCopie a linha acima e envie ao cliente.")
    return 0


def _cli_validate_license():
    print("\n--- Validar uma chave de licença ---\n")
    key = (_safe_input("Cole a chave: ") or '').strip()
    machine_id = (_safe_input("Digite o ID da máquina: ") or '').strip()
    if not key or not machine_id:
        print("Erro: chave e ID são obrigatórios.")
        return 1
    ok, msg = validate_license_key(key, machine_id)
    if ok:
        _, remaining = get_license_time_remaining(key, machine_id)
        print(f"\nOK — {msg}")
        print(f"Tempo restante: {remaining}")
        return 0
    print(f"\nFALHOU — {msg}")
    return 1


def _cli_show_help():
    print("BarPOS License Manager")
    print("=" * 44)
    print("Uso por linha de comando:")
    print("  python license_manager.py                # menu interativo")
    print("  python license_manager.py --gen-keys     # gerar par de chaves")
    print("  python license_manager.py --issue        # gerar licença")
    print("  python license_manager.py --validate     # validar licença")
    print("  python license_manager.py --help         # esta ajuda")
    print("\nNo Pydroid: apenas toque em 'Run' (o menu aparece).")
    return 0


def _cli_menu():
    """Interactive menu — used when no CLI arguments are given.
    Works perfectly inside Pydroid3 where argv is empty."""
    while True:
        print()
        print("=" * 44)
        print("   BarPOS License Manager")
        print("=" * 44)
        print("  1. Gerar par de chaves (primeira vez)")
        print("  2. Gerar licença para um cliente")
        print("  3. Validar uma licença existente")
        print("  4. Ajuda")
        print("  0. Sair")
        print("=" * 44)
        choice = (_safe_input("Escolha uma opção: ") or '').strip()

        if choice == '1':
            _cli_generate_keys()
        elif choice == '2':
            _cli_issue_license()
        elif choice == '3':
            _cli_validate_license()
        elif choice == '4':
            _cli_show_help()
        elif choice == '0':
            print("Até logo.")
            return 0
        elif choice == '':
            # EOF (Pydroid stops feeding stdin) → exit cleanly
            return 0
        else:
            print("Opção inválida.")


def _main(argv):
    if '--help' in argv or '-h' in argv:
        return _cli_show_help()
    if '--gen-keys' in argv:
        return _cli_generate_keys()
    if '--issue' in argv:
        return _cli_issue_license()
    if '--validate' in argv:
        return _cli_validate_license()
    # No arguments → interactive menu (Pydroid-friendly)
    return _cli_menu()


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))