import os
from pathlib import Path
from django.conf import settings

ENV_PATH = Path(settings.BASE_DIR) / '.env'

DEFAULT_ENV_KEYS = {
    'SYSTEM_EMAIL': 'info@rodztutoring.co.za',
    'NOTIFICATION_EMAIL': 'admin@rodztutoring.co.za',
    'EMAIL_HOST': 'smtp.gmail.com',
    'EMAIL_PORT': '587',
    'EMAIL_USE_TLS': 'True',
    'EMAIL_USE_SSL': 'False',
    'EMAIL_HOST_USER': '',
    'EMAIL_HOST_PASSWORD': '',
    'WHATSAPP_PHONE': '27745685212',
    'WHATSAPP_DISPLAY_PHONE': '+27 74 568 5212',
}


def read_env_file():
    """Reads .env into a dictionary of key-value pairs."""
    data = {}
    if not ENV_PATH.exists():
        return data

    with open(ENV_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                data[key.strip()] = val.strip().strip("'\"")
    return data


def update_env_file(updates: dict):
    """
    Updates the .env file with new key-value pairs,
    preserving comments and existing keys.
    """
    lines = []
    found_keys = set()

    if ENV_PATH.exists():
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key, _ = stripped.split('=', 1)
            key = key.strip()
            if key in updates:
                new_val = updates[key]
                new_lines.append(f"{key}={new_val}\n")
                found_keys.add(key)
                continue
        new_lines.append(line)

    # Append any brand-new keys that were not already in the .env file
    for key, val in updates.items():
        if key not in found_keys:
            new_lines.append(f"{key}={val}\n")

    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    # Apply updates directly to Django runtime settings
    for key, val in updates.items():
        if key == 'EMAIL_PORT':
            try:
                setattr(settings, key, int(val))
            except ValueError:
                pass
        elif key in ('EMAIL_USE_TLS', 'EMAIL_USE_SSL', 'DEBUG'):
            setattr(settings, key, val.lower() in ('true', '1', 'yes'))
        elif key == 'SYSTEM_EMAIL':
            setattr(settings, 'DEFAULT_FROM_EMAIL', val)
            setattr(settings, 'SYSTEM_EMAIL', val)
        else:
            setattr(settings, key, val)
