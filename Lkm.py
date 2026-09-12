"""
BarPOS License Manager — single-file module.

Handles:
  • Ed25519 keypair generation
  • License issuance (interactive menu or CLI flags)
  • License validation (Ed25519, with optional legacy HMAC fallback)
  • Encrypted license grants (runtime storage)
  • Human-readable time-remaining formatting

Runtime model:
  1. User activates ONCE by pasting a license key.
     → Lkm.validate_license_key() checks it.
     → Lkm.create_grant() produces an encrypted blob.
     → The blob is stored in the DB. The raw key is discarded.
  2. On every launch after that, main.py reads the encrypted grant
     from the DB, decrypts it locally, and checks the expiry.

Usage (CLI):
    python Lkm.py                # interactive menu
    python Lkm.py --gen-keys     # generate keypair
    python Lkm.py --issue        # issue a license
    python Lkm.py --validate     # validate a key
    python Lkm.py --help
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

# ===========================================================================
# SECURITY SWITCH
#
# ALLOW_LEGACY_VALIDATION = True
#     Old HMAC licenses still validate. Keep True ONLY while migrating
#     existing customers to Ed25519 keys.
#
# ALLOW_LEGACY_VALIDATION = False   ← ship this once everyone is migrated
# ===========================================================================
ALLOW_LEGACY_VALIDATION = True

# ---------------------------------------------------------------------------
# Legacy HMAC secret — used ONLY when ALLOW_LEGACY_VALIDATION is True.
# ---------------------------------------------------------------------------
_LEGACY_SECRET = b"BarPOS_S3cr3t_Lic3ns3_K3y_2024"

# ---------------------------------------------------------------------------
# Ed25519 asymmetric signing (preferred).
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    _HAS_ED25519 = True
except ImportError:
    _HAS_ED25519 = False

# ---------------------------------------------------------------------------
# Fernet (AES) for the encrypted license grant.
# ---------------------------------------------------------------------------
try:
    from cryptography.fernet import Fernet as _Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


# Replace this placeholder with YOUR public key.
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
-----END PUBLIC KEY-----"""

V2_PREFIX = "v2."

DEFAULT_PRIVATE_KEY_PATH = 'license_private.pem'
DEFAULT_PUBLIC_KEY_PATH = 'license_public.pem'

# Application pepper for grant encryption.
APP_PEPPER = b"BarPOS_License_Vault_v1_a7f3c9e2b8d4f1a6"


# ===========================================================================
# Key management
# ===========================================================================
def generate_keypair(private_key_path=DEFAULT_PRIVATE_KEY_PATH,
                     public_key_path=DEFAULT_PUBLIC_KEY_PATH):
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
# Base64 helpers
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
    """Generate a v2 (Ed25519) license. Requires the private key."""
    expiry_dt = _parse_expiry_input(expiry_input)
    payload = {
        "machine_id": machine_id,
        "expiry": expiry_dt.isoformat(),
        "issued": datetime.now().isoformat()
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')

    if not _HAS_ED25519:
        raise RuntimeError(
            "Ed25519 not available. Install: pip install cryptography")
    if not os.path.exists(private_key_path):
        raise RuntimeError(
            f"Private key '{private_key_path}' not found. "
            "Only the developer should have this file.")

    priv = _load_private_key(private_key_path)
    sig = priv.sign(payload_json)
    return V2_PREFIX + _b64encode(payload_json) + "." + _b64encode(sig)


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
    if ALLOW_LEGACY_VALIDATION:
        return _validate_legacy(key, machine_id, current_datetime)
    return False, "Formato de licença não suportado"


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
# Payload decoding (for grant creation)
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
            if not ALLOW_LEGACY_VALIDATION:
                return None
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


# ===========================================================================
# Human-readable time remaining
# ===========================================================================
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
# Encrypted License Grant
# ===========================================================================
def _derive_vault_key(machine_id):
    mid = str(machine_id).encode('utf-8')
    salt = b"BarPOS_Salt_v1_" + mid
    return hashlib.pbkdf2_hmac(
        'sha256',
        APP_PEPPER + mid,
        salt,
        200_000,
        dklen=32
    )


def _fernet_for(machine_id):
    key = base64.urlsafe_b64encode(_derive_vault_key(machine_id))
    return _Fernet(key)


def _keystream(key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.pbkdf2_hmac(
            'sha256', key, nonce + counter.to_bytes(4, 'big'), 1, dklen=32)
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _encrypt_payload(machine_id, plaintext_bytes):
    if _HAS_FERNET:
        return _fernet_for(machine_id).encrypt(plaintext_bytes).decode('ascii')
    key = _derive_vault_key(machine_id)
    nonce = os.urandom(16)
    stream = _keystream(key, nonce, len(plaintext_bytes))
    ct = bytes(a ^ b for a, b in zip(plaintext_bytes, stream))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    blob = nonce + ct + mac
    return base64.urlsafe_b64encode(blob).decode('ascii').rstrip('=')


def _decrypt_payload(machine_id, blob_str):
    if _HAS_FERNET:
        try:
            return _fernet_for(machine_id).decrypt(blob_str.encode('ascii'))
        except Exception:
            return None
    try:
        padding = '=' * (-len(blob_str) % 4)
        blob = base64.urlsafe_b64decode(blob_str + padding)
        if len(blob) < 48:
            return None
        nonce = blob[:16]
        ct = blob[16:-32]
        mac = blob[-32:]
        key = _derive_vault_key(machine_id)
        expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):
            return None
        stream = _keystream(key, nonce, len(ct))
        return bytes(a ^ b for a, b in zip(ct, stream))
    except Exception:
        return None


def create_grant(license_key, machine_id):
    """Create an encrypted grant blob from a VALIDATED license key."""
    payload = get_license_payload(license_key)
    if payload is None:
        raise ValueError("Chave de licença inválida ou formato não suportado")
    grant = {
        'v': 1,
        'app': 'barpos',
        'machine_id': machine_id,
        'expiry': payload.get('expiry'),
        'created_at': datetime.now().isoformat(),
        'key_hash': hashlib.sha256(
            license_key.encode('utf-8')).hexdigest()[:16],
    }
    plaintext = json.dumps(grant, separators=(',', ':')).encode('utf-8')
    return _encrypt_payload(machine_id, plaintext)


def read_grant(blob_str, machine_id):
    """Decrypt and return the grant dict, or None if invalid."""
    if not blob_str:
        return None
    plaintext = _decrypt_payload(machine_id, blob_str)
    if plaintext is None:
        return None
    try:
        grant = json.loads(plaintext.decode('utf-8'))
    except Exception:
        return None
    if not isinstance(grant, dict):
        return None
    if grant.get('app') != 'barpos':
        return None
    if grant.get('machine_id') != machine_id:
        return None
    return grant


def is_grant_valid(grant, current_datetime=None):
    """Return (valid, message). If valid, message is time left."""
    if not grant:
        return False, "Sem licença"
    expiry_str = grant.get('expiry')
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
    try:
        return input(prompt)
    except EOFError:
        return None


def _cli_generate_keys():
    print("\n--- Gerar par de chaves Ed25519 ---\n")
    if not _HAS_ED25519:
        print("ERRO: A biblioteca 'cryptography' não está instalada.")
        print("Instale com: pip install cryptography")
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
        print("\n--- COPIE O BLOCO ABAIXO PARA 'PUBLIC_KEY_PEM' EM Lkm.py ---\n")
        print(pub.decode())
        print("--- FIM ---\n")
        print("NUNCA envie license_private.pem no APK.")
        return 0
    except Exception as e:
        print(f"Erro: {e}")
        return 1


def _cli_issue_license():
    print("\n--- Gerar licença para um cliente ---\n")
    if not _HAS_ED25519:
        print("ERRO: 'cryptography' não instalada.")
        return 1
    if not os.path.exists(DEFAULT_PRIVATE_KEY_PATH):
        print(f"ERRO: '{DEFAULT_PRIVATE_KEY_PATH}' não encontrado.")
        print("Rode a opção 1 do menu para gerar o par de chaves.")
        return 1
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
    except (ValueError, RuntimeError) as e:
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
    print("BarPOS License Manager (Lkm)")
    print("=" * 44)
    print("  python Lkm.py                # menu interativo")
    print("  python Lkm.py --gen-keys     # gerar par de chaves")
    print("  python Lkm.py --issue        # gerar licença")
    print("  python Lkm.py --validate     # validar licença")
    print("  python Lkm.py --help         # esta ajuda")
    print(f"\nLegacy validation: "
          f"{'ENABLED (insecure!)' if ALLOW_LEGACY_VALIDATION else 'DISABLED (secure)'}")
    return 0


def _cli_menu():
    while True:
        print()
        print("=" * 44)
        print("   BarPOS License Manager (Lkm)")
        print("=" * 44)
        if ALLOW_LEGACY_VALIDATION:
            print("   Legacy HMAC: LIGADO (inseguro)")
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
    return _cli_menu()


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))