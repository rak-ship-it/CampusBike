"""Admin login throttle and conservative response headers."""
import hashlib
import time
from contextlib import closing
from flask import request


def register_admin_security(app,get_db):
    @app.before_request
    def limit_admin_login():
        if request.path!='/admin/login' or request.method!='POST':
            return None
        key=hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
        now=int(time.time())
        with closing(get_db()) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM admin_login_limits WHERE window_start<?',(now-900,))
            row=db.execute('SELECT attempts FROM admin_login_limits WHERE key=?',(key,)).fetchone()
            if row and row['attempts']>=10:
                db.commit()
                return 'Too many admin login attempts. Try again in 15 minutes.',429,{'Retry-After':'900'}
            db.execute('INSERT INTO admin_login_limits VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1',(key,now))
            db.commit()

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers['Referrer-Policy']='same-origin'
        if request.path.startswith('/admin'):
            response.headers['Cache-Control']='no-store'
        return response
