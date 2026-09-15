"""Opaque, revocable mobile sessions. Raw tokens/passwords are never stored."""
import hashlib
import os
import secrets
import time
from contextlib import closing

from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

SESSION_SECONDS = 24 * 60 * 60
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(24))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def register_mobile_auth(blueprint, get_db):
    def error(message, status):
        return jsonify(success=False, message=message), status

    def dev_enabled():
        return os.environ.get('CAMPUSBIKE_DEV_LOGIN', '0') == '1'

    @blueprint.before_request
    def authenticate():
        if request.endpoint in {'mobile_api.health', 'mobile_api.login', 'mobile_api.dev_login', 'mobile_api.auth_config'}:
            return None
        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith('Bearer ') or len(authorization) > 256:
            return error('Please sign in again.', 401)
        digest = token_hash(authorization[7:])
        with closing(get_db()) as db:
            row = db.execute('''
                SELECT s.student_id, s.name, s.email, s.active, t.expires_at, t.kind
                FROM mobile_sessions t JOIN students s ON s.student_id=t.student_id
                WHERE t.token_hash=?
            ''', (digest,)).fetchone()
        if not row or row['expires_at'] <= int(time.time()) or row['active'] != 1:
            return error('Your session has expired. Please sign in again.', 401)
        if row['kind'] == 'dev' and not dev_enabled():
            return error('Development login is disabled. Please sign in again.', 401)
        from ride_returns import expire_reservations
        with closing(get_db()) as db:
            expire_reservations(db)
            db.commit()
        g.student_id = row['student_id']
        g.mobile_student = {key: row[key] for key in ('student_id', 'name', 'email')}
        g.mobile_token_hash = digest
        # Old clients may still send IDs. Reject mismatches before any action.
        identities = [request.view_args.get('student_id')] if request.view_args else []
        identities.extend(request.args.getlist('student_id'))
        if request.is_json:
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return error('Expected a JSON object.', 400)
            if 'student_id' in data:
                identities.append(data['student_id'])
        if any(str(value).strip().upper() != g.student_id for value in identities if value is not None):
            return error('You can only access your own account.', 403)

    @blueprint.after_request
    def no_auth_cache(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    @blueprint.route('/auth/config')
    def auth_config():
        return jsonify(dev_login_enabled=dev_enabled())

    def sign_in(development=False):
        if development and not dev_enabled():
            return error('Development login is disabled.', 403)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error('Expected a JSON object.', 400)
        student_id = str(data.get('student_id', '')).strip().upper()
        password = data.get('password', '')
        if not student_id or len(student_id) > 100 or not isinstance(password, str) or len(password) > 1024:
            return error('Invalid student ID or password.', 401)
        if development:
            from database import DEFAULT_STUDENTS
            if student_id not in DEFAULT_STUDENTS:
                return error('Development login is limited to test accounts.', 403)
        now = int(time.time())
        with closing(get_db()) as db:
            # Persistent account throttle, shared by Flask workers/restarts.
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM mobile_login_attempts WHERE window_start < ?', (now - 900,))
            attempt = db.execute('SELECT failures FROM mobile_login_attempts WHERE student_id=?', (student_id,)).fetchone()
            if attempt and attempt['failures'] >= 5:
                db.rollback()
                return error('Too many login attempts. Try again in 15 minutes.', 429)
            row = db.execute('SELECT student_id,name,email,active,password_hash FROM students WHERE student_id=?', (student_id,)).fetchone()
            valid_password = development or check_password_hash((row['password_hash'] if row else None) or DUMMY_HASH, password)
            if not row or row['active'] != 1 or not valid_password:
                db.execute('''INSERT INTO mobile_login_attempts(student_id, failures, window_start)
                    VALUES (?,1,?) ON CONFLICT(student_id) DO UPDATE SET failures=failures+1''', (student_id, now))
                db.commit()
                return error('Invalid student ID or password.', 401)
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM mobile_login_attempts WHERE student_id=?', (student_id,))
            db.execute('DELETE FROM mobile_sessions WHERE expires_at <= ?', (now,))
            db.execute('INSERT INTO mobile_sessions VALUES (?,?,?,?,?)',
                       (token_hash(token), student_id, now, now + SESSION_SECONDS, 'dev' if development else 'password'))
            db.commit()
        return jsonify(success=True, student={key: row[key] for key in ('student_id','name','email')},
                       access_token=token, expires_at=now + SESSION_SECONDS)

    @blueprint.route('/login', methods=['POST'])
    def login():
        return sign_in()

    @blueprint.route('/dev-login', methods=['POST'])
    def dev_login():
        return sign_in(development=True)

    @blueprint.route('/me')
    def me():
        return jsonify(success=True, student=g.mobile_student)

    @blueprint.route('/logout', methods=['POST'])
    def logout():
        with closing(get_db()) as db:
            db.execute('DELETE FROM mobile_sessions WHERE token_hash=?', (g.mobile_token_hash,))
            db.commit()
        return jsonify(success=True)
