import time
from test_return_flow import FlowTestCase


class StudentDemoTests(FlowTestCase):
    def test_created_student_can_complete_ride(self):
        password = 'new-demo-student-password'
        self.client.post('/admin/accounts', data=dict(action='create', student_id='DEMO006', name='Demo Student', password=password))
        student = self.web.app.test_client()
        login = student.post('/api/login', json=dict(student_id='DEMO006', password=password))
        self.assertEqual(login.status_code, 200, login.json)
        student.environ_base['HTTP_AUTHORIZATION'] = 'Bearer ' + login.json['access_token']
        rented = student.post('/api/rent', json=self.rent_payload(student='DEMO006'))
        self.assertEqual(rented.status_code, 200, rented.json)
        ride = student.get('/api/students/DEMO006/active-ride').json['active_ride']
        reserved = student.post('/api/reserve-return-slot', json=dict(ride_id=ride['ride_id'], station_id=2,
            location_samples=[dict(latitude=18.65, longitude=73.77, accuracy=5, timestamp=int(time.time()*1000)) for _ in range(3)]))
        self.assertEqual(reserved.status_code, 200, reserved.json)
        slot = reserved.json['reservation']['slot']
        returned = student.post('/api/end-ride', json=dict(ride_id=ride['ride_id'], station_id=2, slot_number=slot))
        self.assertEqual(returned.status_code, 200, returned.json)
        history = student.get('/api/students/DEMO006/rides').json
        self.assertEqual(history['total_rides'], 1)
        self.assertEqual(history['rides'][0]['return_slot'], slot)
        self.client.post('/admin/accounts', data=dict(action='disable', student_id='DEMO006'))
        self.assertEqual(student.get('/api/students/DEMO006/active-ride').status_code, 401)

    def test_report_identification_does_not_rent(self):
        identified = self.client.post('/api/bike-by-qr', json=dict(purpose='report', qr_token=self.rent_payload()['qr_token']))
        self.assertEqual(identified.status_code, 200, identified.json)
        self.assertEqual(identified.json['bike']['bike_id'], 'CB001')
        self.assertIsNone(self.active())
        report = self.client.post('/api/maintenance-reports', json=dict(bike_id='CB001', issue_type='Tyre', description='Flat rear tyre', severity='High'))
        self.assertEqual(report.status_code, 201, report.json)
        self.assertIsNone(self.active())
        self.assertTrue(self.query("SELECT * FROM maintenance_reports WHERE bike_id='CB001' AND description='Flat rear tyre'"))

    def test_report_scan_accepts_in_use_bike_but_rental_scan_does_not(self):
        qr = self.rent_payload()['qr_token']
        self.post('rent', self.rent_payload())
        response = self.client.post('/api/bike-by-qr', json=dict(qr_token=qr, purpose='report'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post('/api/bike-by-qr', json=dict(qr_token=qr)).status_code, 409)
        self.assertEqual(self.client.post('/api/bike-by-qr', json=dict(qr_token='invalid', purpose='report')).status_code, 404)
