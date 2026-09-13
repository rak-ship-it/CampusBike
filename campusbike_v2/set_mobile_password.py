"""Admin-only local provisioning: python set_mobile_password.py STU001."""
import argparse
import getpass
import sqlite3
from contextlib import closing
from werkzeug.security import generate_password_hash
from database import DB_NAME, initialize_database


def set_password(student_id, password, db_name=DB_NAME):
    if not 12 <= len(password) <= 128:
        raise ValueError('Use a password between 12 and 128 characters.')
    with closing(sqlite3.connect(db_name)) as db:
        db.execute('BEGIN IMMEDIATE')
        result = db.execute('UPDATE students SET password_hash=? WHERE student_id=? AND active=1',
                            (generate_password_hash(password), student_id.strip().upper()))
        if result.rowcount != 1:
            raise ValueError('Active student not found.')
        db.execute('DELETE FROM mobile_sessions WHERE student_id=?', (student_id.strip().upper(),))
        db.execute('DELETE FROM mobile_login_attempts WHERE student_id=?', (student_id.strip().upper(),))
        db.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('student_id')
    args = parser.parse_args()
    password = getpass.getpass('New mobile password (12+ characters): ')
    if password != getpass.getpass('Confirm password: '):
        parser.error('Passwords do not match.')
    initialize_database()
    try:
        set_password(args.student_id, password)
    except ValueError as error:
        parser.error(str(error))
    print('Mobile password set; existing sessions revoked.')
