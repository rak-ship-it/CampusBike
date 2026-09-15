"""Resolve configuration relative to this backend, not the terminal directory."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR=Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
DB_NAME=os.environ.get('CAMPUSBIKE_DB_PATH',str(BASE_DIR / 'campusbike.db'))
if not Path(DB_NAME).is_absolute():
    DB_NAME=str(BASE_DIR / DB_NAME)


def validate_deployment():
    if os.environ.get('CAMPUSBIKE_ENV','development')!='production':
        return
    secret=os.environ.get('SECRET_KEY','')
    password=os.environ.get('ADMIN_PASSWORD','')
    if len(secret)<32 or secret.startswith(('change-','replace-')):
        raise RuntimeError('Production requires a random SECRET_KEY of at least 32 characters.')
    if len(password)<12 or password.startswith('change-'):
        raise RuntimeError('Production requires a unique ADMIN_PASSWORD of at least 12 characters.')
    if os.environ.get('CAMPUSBIKE_DEV_LOGIN','0')!='0' or os.environ.get('FLASK_DEBUG','0')!='0':
        raise RuntimeError('Development login and debug must be disabled in production.')
    if os.environ.get('SESSION_COOKIE_SECURE','0')!='1':
        raise RuntimeError('Production requires HTTPS and SESSION_COOKIE_SECURE=1.')
