import os
import textwrap

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import keyring
except Exception:
    keyring = None


def check_env():
    user = os.environ.get('TRINO_USER')
    pwd = os.environ.get('TRINO_PASSWORD')
    token = os.environ.get('TRINO_BEARER_TOKEN')
    return user, pwd, token


def check_keyring(user):
    if not keyring or not user:
        return None
    try:
        return keyring.get_password('trino', user)
    except Exception:
        return None


def generate_report():
    user, pwd, token = check_env()
    kr_pwd = check_keyring(user)

    lines = []
    lines.append('Trino Credentials Report')
    lines.append('========================')
    lines.append('')

    lines.append('Environment')
    lines.append('-----------')
    lines.append(f"TRINO_USER: {'SET' if user else 'NOT SET'}")
    lines.append(f"TRINO_PASSWORD: {'SET' if pwd else 'NOT SET'}")
    lines.append(f"TRINO_BEARER_TOKEN: {'SET' if token else 'NOT SET'}")
    lines.append('')

    lines.append('Keyring')
    lines.append('-------')
    if keyring:
        if user:
            lines.append(f"Keyring available: YES (service='trino', user='{user}')")
            lines.append(f"Password in keyring: {'FOUND' if kr_pwd else 'NOT FOUND'}")
        else:
            lines.append('Keyring available: YES')
            lines.append('No TRINO_USER set, cannot query keyring for password.')
    else:
        lines.append('Keyring available: NO')
    lines.append('')

    lines.append('Recommendations')
    lines.append('---------------')
    if token:
        lines.append('- You are using a Bearer token (TRINO_BEARER_TOKEN). Ensure it is stored securely and rotated per policy.')
    elif user and pwd:
        lines.append('- TRINO_USER and TRINO_PASSWORD are set in the environment. Consider removing TRINO_PASSWORD from env and storing it in the OS keyring for safety.')
    elif user and kr_pwd:
        lines.append('- TRINO_USER is set and password found in keyring: good. Prefer this over env variables.')
    elif user and not kr_pwd and not pwd:
        lines.append('- TRINO_USER set but no password found. Either set TRINO_PASSWORD env (temporary) or store password with keyring.')
    else:
        lines.append('- No usable credentials found. Set TRINO_BEARER_TOKEN or TRINO_USER+password (env or keyring).')

    lines.append('\nQuick commands')
    lines.append('--------------')
    lines.append("# Save a password to the OS keyring:\npython -c \"import keyring; keyring.set_password('trino','<user>','<password>')\"")
    lines.append("# Set a temporary env (PowerShell):\n$env:TRINO_USER='<user>'; $env:TRINO_PASSWORD='<password>'")

    print(textwrap.dedent('\n'.join(lines)))


if __name__ == '__main__':
    generate_report()
