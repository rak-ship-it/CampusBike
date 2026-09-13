"""Authorization regressions with real Flask routes and disposable SQLite."""
import os
import time
from unittest.mock import patch
from test_return_flow import FlowTestCase
from set_mobile_password import set_password
from mobile_auth import token_hash


class MobileAuthTests(FlowTestCase):
    def test_missing_invalid_expired_and_revoked_tokens(self):
        client = self.web.app.test_client()
        for headers in ({}, {'Authorization': 'Bearer invalid'}):
            self.assertEqual(client.get('/api/students/STU001/rides', headers=headers).status_code, 401)
        self.query('UPDATE mobile_sessions SET expires_at=?', (int(time.time())-1,))
        self.assertEqual(self.client.get('/api/me').status_code, 401)

    def test_password_verification_and_throttle(self):
        client = self.web.app.test_client()
        for _ in range(5):
            response = client.post('/api/login', json={'student_id': 'STU002', 'password': 'wrong'})
            self.assertEqual(response.status_code, 401)
        response = client.post('/api/login', json={'student_id':'STU002','password':'test-password-for-suite'})
        self.assertEqual(response.status_code, 429)
        self.query('UPDATE mobile_login_attempts SET window_start=?', (int(time.time())-901,))
        self.assertEqual(client.post('/api/login', json={'student_id':'STU002','password':'test-password-for-suite'}).status_code, 200)
        self.assertNotEqual(self.query("SELECT password_hash FROM students WHERE student_id='STU001'")[0]['password_hash'], 'test-password-for-suite')
        self.assertTrue(self.query('SELECT * FROM mobile_sessions WHERE token_hash=?', (token_hash(self.token),)))
        self.assertFalse(self.query('SELECT * FROM mobile_sessions WHERE token_hash=?', (self.token,)))

    def test_cross_student_reads_and_writes_are_forbidden(self):
        for route in ('rides','active-ride'):
            self.assertEqual(self.client.get('/api/students/STU002/'+route).status_code,403)
        before = self.query('SELECT * FROM bikes')
        for route in ('rent','reserve-return-slot','cancel-return-slot','end-ride','maintenance-reports'):
            self.assertEqual(self.client.post('/api/'+route, json={'student_id':'STU002'}).status_code,403)
        self.assertEqual(self.query('SELECT * FROM bikes'), before)

    def test_write_identity_comes_from_session(self):
        payload = self.rent_payload()
        del payload['student_id']
        self.post('rent', payload)
        self.assertEqual(self.query('SELECT student_id FROM rides')[0]['student_id'],'STU001')

    def test_logout_and_password_reset_revoke_sessions(self):
        self.assertEqual(self.client.post('/api/logout').status_code,200)
        self.assertEqual(self.client.get('/api/me').status_code,401)
        login = self.client.post('/api/login', json={'student_id':'STU001','password':'test-password-for-suite'})
        self.client.environ_base['HTTP_AUTHORIZATION']='Bearer '+login.json['access_token']
        set_password('STU001','new-test-password-123',self.path)
        self.assertEqual(self.client.get('/api/me').status_code,401)
        self.assertEqual(self.client.post('/api/login',json={'student_id':'STU001','password':'test-password-for-suite'}).status_code,401)
        self.assertEqual(self.client.post('/api/login',json={'student_id':'STU001','password':'new-test-password-123'}).status_code,200)

    def test_inactive_account_and_dev_switch(self):
        with patch.dict(os.environ, {'CAMPUSBIKE_DEV_LOGIN':'0'}):
            self.assertEqual(self.client.post('/api/dev-login',json={'student_id':'STU001'}).status_code,403)
        with patch.dict(os.environ, {'CAMPUSBIKE_DEV_LOGIN':'1'}):
            login=self.client.post('/api/dev-login',json={'student_id':'STU002'})
            self.assertEqual(login.status_code,200)
            dev_headers={'Authorization':'Bearer '+login.json['access_token']}
            self.assertEqual(self.client.get('/api/me',headers=dev_headers).status_code,200)
        with patch.dict(os.environ, {'CAMPUSBIKE_DEV_LOGIN':'0'}):
            self.assertEqual(self.client.get('/api/me',headers=dev_headers).status_code,401)
        self.query("UPDATE students SET active=0 WHERE student_id='STU001'")
        self.assertEqual(self.client.get('/api/me').status_code,401)

    def test_malformed_json_and_no_cache(self):
        self.assertEqual(self.client.post('/api/login',json=[]).status_code,400)
        self.assertEqual(self.client.post('/api/end-ride',json=[]).status_code,400)
        self.assertEqual(self.client.get('/api/me').headers['Cache-Control'],'no-store')
