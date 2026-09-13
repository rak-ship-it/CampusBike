"""Run with python -m unittest discover -s campusbike_v2/tests -v.

All writes use temporary databases; no Codespace data or real GPS is used.
"""
import importlib
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
import mobile_api
from werkzeug.security import generate_password_hash


class FlowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # app.py initializes on import: redirect even that first write.
        cls.password_hash = generate_password_hash('test-password-for-suite')
        cls.boot = tempfile.TemporaryDirectory()
        initialize = database.initialize_database
        with patch.object(database, 'DB_NAME', cls.boot.name + '/boot.db'), patch.object(
            database, 'initialize_database', lambda: initialize(cls.boot.name + '/boot.db')
        ):
            cls.web = importlib.import_module('app')
        cls.web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    @classmethod
    def tearDownClass(cls):
        cls.boot.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = self.temp.name + '/test.db'
        database.initialize_database(self.path)
        for module in (mobile_api, self.web):
            patcher = patch.object(module, 'DB_NAME', self.path)
            patcher.start()
            self.addCleanup(patcher.stop)
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE students SET password_hash=?', (self.password_hash,))
        self.client = self.web.app.test_client()
        login = self.client.post('/api/login', json={'student_id': 'STU001', 'password': 'test-password-for-suite'})
        self.assertEqual(login.status_code, 200, login.json)
        self.token = login.json['access_token']
        self.client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer ' + self.token
        with self.client.session_transaction() as session:
            session['admin_logged_in'] = True
            session['admin_username'] = 'test-admin'

    def query(self, sql, args=()):
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(sql, args)]

    def post(self, route, payload, expected=200):
        response = self.client.post('/api/' + route, json=payload)
        self.assertEqual(response.status_code, expected, response.json)
        return response.json

    def rent_payload(self, bike='CB001', student='STU001'):
        token = self.query('SELECT qr_secret FROM bikes WHERE bike_id=?', (bike,))[0]['qr_secret']
        return dict(bike_id=bike, student_id=student, qr_token=f'CAMPUSBIKE|{bike}|{token}')

    def reserve(self, station=2, student='STU001'):
        return self.post('reserve-return-slot', dict(student_id=student, station_id=station))['reservation']

    def active(self):
        return self.client.get('/api/students/STU001/active-ride').json['active_ride']


class ReturnFlowTests(FlowTestCase):
    def test_first_boot_rent_reserve_restart_confirm_history(self):
        self.post('rent', self.rent_payload())
        reservation = self.reserve()
        self.assertEqual(self.active()['reserved_return_slot'], reservation['slot'])
        self.assertIsNone(self.query('SELECT returned_at FROM rides')[0]['returned_at'])
        self.assertEqual(self.query("SELECT status FROM bikes WHERE bike_id='CB001'")[0]['status'], 'In use')
        self.assertEqual(self.reserve(), reservation)
        database.initialize_database(self.path)
        self.assertEqual(self.active()['reserved_return_slot'], reservation['slot'])
        payload = dict(student_id='STU001', station_id=2, slot_number=reservation['slot'])
        self.post('end-ride', dict(payload, slot_number='SLOT-99'), 409)
        self.post('end-ride', payload)
        bike = self.query("SELECT * FROM bikes WHERE bike_id='CB001'")[0]
        self.assertEqual((bike['status'], bike['lock_status'], bike['total_rides']), ('Available', 'Locked', 1))
        dock = self.query('SELECT * FROM slots WHERE station_id=2 AND slot_number=?', (reservation['slot'],))[0]
        self.assertEqual((dock['status'], dock['bike_id']), ('Occupied', 'CB001'))
        self.assertIsNone(self.active())
        history = self.client.get('/api/students/STU001/rides').json
        self.assertEqual(history['total_rides'], 1)
        self.assertEqual(history['rides'][0]['return_slot'], reservation['slot'])
        self.post('end-ride', payload, 409)
        database.initialize_database(self.path)
        bike = self.query("SELECT station_id, slot, total_rides FROM bikes WHERE bike_id='CB001'")[0]
        self.assertEqual(bike, dict(station_id=2, slot=reservation['slot'], total_rides=1))

    def test_cancel_then_change_station(self):
        self.post('rent', self.rent_payload())
        reservation = self.reserve()
        self.post('reserve-return-slot', dict(student_id='STU001', station_id=3), 409)
        self.post('cancel-return-slot', dict(student_id='STU001'))
        self.post('cancel-return-slot', dict(student_id='STU001'))
        self.assertIsNotNone(self.active())
        self.assertEqual(self.query('SELECT status FROM slots WHERE station_id=2 AND slot_number=?', (reservation['slot'],))[0]['status'], 'Available')
        self.assertEqual(self.reserve(3)['station_id'], 3)

    def test_full_and_inactive_stations(self):
        self.post('rent', self.rent_payload())
        self.query("UPDATE slots SET status='Maintenance' WHERE station_id=2")
        self.post('reserve-return-slot', dict(student_id='STU001', station_id=2), 409)
        self.query('UPDATE stations SET active=0 WHERE station_id=3')
        self.post('reserve-return-slot', dict(student_id='STU001', station_id=3), 409)
        self.assertIsNotNone(self.active())

    def test_maintenance_return_stays_unavailable(self):
        self.post('rent', self.rent_payload())
        reservation = self.reserve()
        self.post('maintenance-reports', dict(student_id='STU001', bike_id='CB001', issue_type='Brake', description='Test brake report'), 201)
        result = self.post('end-ride', dict(student_id='STU001', station_id=2, slot_number=reservation['slot']))
        self.assertEqual(result['return']['bike_status'], 'Maintenance')

    def test_simultaneous_rentals_one_student(self):
        barrier = threading.Barrier(2)
        payloads = [self.rent_payload(bike) for bike in ('CB001', 'CB002')]
        def rent(payload):
            with self.web.app.test_client() as client:
                barrier.wait(timeout=5)
                return client.post('/api/rent', json=payload, headers={'Authorization': 'Bearer ' + self.token}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(rent, payloads)), [200, 409])
        self.assertEqual(len(self.query('SELECT * FROM rides WHERE returned_at IS NULL')), 1)

    def test_rebalancing_restart_complete_and_cancel(self):
        for action in ('complete', 'cancel'):
            with self.subTest(action=action):
                source = self.query("SELECT station_id, slot FROM bikes WHERE bike_id='CB001'")[0]
                destination = 2 if source['station_id'] != 2 else 3
                self.client.post('/admin/fleet/CB001/rebalance', data={'destination_station_id': destination})
                self.assertEqual(self.query("SELECT status FROM bikes WHERE bike_id='CB001'")[0]['status'], 'Rebalancing')
                reserved = self.query("SELECT station_id, slot_number FROM slots WHERE bike_id='CB001' AND status='Reserved'")
                self.assertEqual(len(reserved), 1)
                database.initialize_database(self.path)
                self.assertEqual(self.query("SELECT status FROM bikes WHERE bike_id='CB001'")[0]['status'], 'Rebalancing')
                self.assertEqual(self.query("SELECT station_id, slot_number FROM slots WHERE bike_id='CB001' AND status='Reserved'"), reserved)
                self.client.post('/admin/fleet/CB001/rebalance/' + action)
                bike = self.query("SELECT status, station_id, slot FROM bikes WHERE bike_id='CB001'")[0]
                self.assertEqual(bike['status'], 'Available')
                self.assertEqual(bike['station_id'], destination if action == 'complete' else source['station_id'])
                self.assertEqual(bike['slot'], reserved[0]['slot_number'] if action == 'complete' else source['slot'])
                self.assertFalse(self.query("SELECT * FROM slots WHERE bike_id='CB001' AND status='Reserved'"))


if __name__ == '__main__':
    unittest.main()
