"""Create local configuration without overwriting existing settings."""
import getpass
import json
import os
import secrets
from pathlib import Path

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    env=root/'.env'
    if env.exists():
        raise SystemExit('Existing .env preserved. Edit it manually using .env.example as a reference.')
    password=getpass.getpass('Choose admin password (12+ characters): ')
    if len(password)<12 or len(password)>128 or '\n' in password or '\r' in password or '${' in password:
        raise SystemExit('Use 12-128 characters, without line breaks or ${ sequences.')
    if password!=getpass.getpass('Confirm admin password: '):
        raise SystemExit('Passwords did not match.')
    fd=os.open(env,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as handle:
        handle.write('SECRET_KEY='+secrets.token_hex(32)+'\nADMIN_USERNAME=admin\nADMIN_PASSWORD='+json.dumps(password)+'\nCAMPUSBIKE_ENV=development\nCAMPUSBIKE_DEV_LOGIN=0\nCAMPUSBIKE_SIMULATED_DOCKS=1\nSESSION_COOKIE_SECURE=0\nFLASK_DEBUG=0\n')
    codespace=os.environ.get('CODESPACE_NAME')
    mobile=root.parent/'CampusBikeMobile'/'.env'
    if codespace and not mobile.exists():
        mobile.write_text('EXPO_PUBLIC_API_BASE_URL=https://'+codespace+'-5000.app.github.dev\n')
    print('Configuration created. Set a student password, start the backend, and configure the mobile backend URL.')
