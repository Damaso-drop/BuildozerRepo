import hmac
import hashlib
import base64
import json
import time
import re
from datetime import datetime, date, timedelta

SECRET_KEY = b"BarPOS_S3cr3t_Lic3ns3_K3y_2024"

def _sign(payload_bytes):
    return hmac.new(SECRET_KEY, payload_bytes, hashlib.sha256).digest()

def _b64encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')

def _b64decode(data):
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

def _parse_expiry_input(expiry_input):
    now = datetime.now()
    match = re.fullmatch(r'(\d+)\s*([smhd])', expiry_input.strip().lower())
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        if unit == 's':
            delta = timedelta(seconds=value)
        elif unit == 'm':
            delta = timedelta(minutes=value)
        elif unit == 'h':
            delta = timedelta(hours=value)
        elif unit == 'd':
            delta = timedelta(days=value)
        else:
            raise ValueError("Unidade inválida")
        return now + delta

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

def generate_license_key(machine_id, expiry_input):
    expiry_dt = _parse_expiry_input(expiry_input)
    payload = {
        "machine_id": machine_id,
        "expiry": expiry_dt.isoformat(),
        "issued": datetime.now().isoformat()
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = _sign(payload_json)
    return _b64encode(payload_json) + "." + _b64encode(signature)

def validate_license_key(key, machine_id, current_datetime=None):
    if not key or '.' not in key:
        return False, "Chave inválida"
    try:
        payload_b64, sig_b64 = key.split('.', 1)
        payload_json = _b64decode(payload_b64)
        signature = _b64decode(sig_b64)
        expected_sig = _sign(payload_json)
        if not hmac.compare_digest(signature, expected_sig):
            return False, "Assinatura inválida"
        payload = json.loads(payload_json.decode('utf-8'))
        if payload.get('machine_id') != machine_id:
            return False, "Chave não pertence a este dispositivo"
        expiry_str = payload.get('expiry')
        if not expiry_str:
            return False, "Data de expiração ausente"
        try:
            expiry_dt = datetime.fromisoformat(expiry_str)
        except ValueError:
            expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        current = current_datetime or datetime.now()
        if current > expiry_dt:
            return False, "Licença expirada"
        return True, "Licença válida"
    except Exception:
        return False, "Erro ao validar chave"

def check_time_tampering(last_seen, current_time=None):
    if current_time is None:
        current_time = time.time()
    if last_seen is None:
        return False, current_time
    tolerance = 60
    if current_time < last_seen - tolerance:
        return True, last_seen
    return False, max(current_time, last_seen)

if __name__ == '__main__':
    print("=== Gerador de Licença BarPOS ===")
    machine_id = input("Digite o ID da máquina: ").strip()
    expiry_input = input("Digite a expiração (ex: 2025-12-31, 2h, 30m, 1d): ").strip()
    if not machine_id or not expiry_input:
        print("Erro: ID e expiração são obrigatórios.")
        exit(1)
    try:
        key = generate_license_key(machine_id, expiry_input)
        print("\nSua chave de licença:")
        print(key)
        print("\nCopie esta chave e envie ao cliente.")
    except ValueError as e:
        print(f"Erro: {e}")
        exit(1)