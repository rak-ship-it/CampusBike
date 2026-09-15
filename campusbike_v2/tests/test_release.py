import os
import time
import sqlite3
from pathlib import Path
from unittest.mock import patch
from test_return_flow import FlowTestCase
from manage import copy_database, audit
from settings import validate_deployment


class ReleaseTests(FlowTestCase):
    def sample_payload(self):
        return dict(student_id='STU001',ride_id=self.active()['ride_id'],station_id=2,
                    location_samples=[dict(latitude=18.65,longitude=73.77,accuracy=5,timestamp=int(time.time()*1000)) for _ in range(3)])

    def test_gps_required_far_stale_and_nonfinite(self):
        self.post('rent',self.rent_payload())
        payload=self.sample_payload()
        missing=dict(payload);missing.pop('location_samples')
        self.assertEqual(self.client.post('/api/reserve-return-slot',json=missing).status_code,400)
        for key,value,expected in [('latitude',0,403),('accuracy',1000,400),('timestamp',0,400),('longitude',float('nan'),400)]:
            invalid={**payload,'location_samples':[{**s,key:value} for s in payload['location_samples']]}
            self.assertEqual(self.client.post('/api/reserve-return-slot',json=invalid).status_code,expected)
        self.assertFalse(self.query("SELECT * FROM slots WHERE status='Reserved'"))

    def test_expiry_releases_dock_without_ending_ride(self):
        self.post('rent',self.rent_payload());reservation=self.reserve()
        self.query("UPDATE slots SET reserved_until=? WHERE bike_id='CB001'",(int(time.time())-1,))
        self.assertNotIn('reserved_return_slot',self.active())
        self.post('end-ride',dict(ride_id=reservation['ride_id'],station_id=2,slot_number=reservation['slot']),409)
        self.assertEqual(self.query("SELECT status FROM bikes WHERE bike_id='CB001'")[0]['status'],'In use')
        self.assertEqual(self.reserve()['slot'],reservation['slot'])

    def test_no_legacy_return_and_retry_cannot_end_new_ride(self):
        self.post('rent',self.rent_payload())
        self.post('end-ride',dict(station_id=2),409)
        assigned=self.reserve();payload=dict(ride_id=assigned['ride_id'],station_id=2,slot_number=assigned['slot'])
        first=self.post('end-ride',payload)
        self.post('rent',self.rent_payload())
        self.assertEqual(self.post('end-ride',payload),first)
        self.assertIsNotNone(self.active())
        self.post('cancel-return-slot',dict(ride_id=assigned['ride_id']),409)
        self.assertEqual(self.query("SELECT total_rides FROM bikes WHERE bike_id='CB001'")[0]['total_rides'],1)

    def test_physical_mode_fails_closed(self):
        self.post('rent',self.rent_payload());assigned=self.reserve()
        with patch.dict(os.environ,{'CAMPUSBIKE_SIMULATED_DOCKS':'0'}):
            self.post('end-ride',dict(ride_id=assigned['ride_id'],station_id=2,slot_number=assigned['slot']),503)
        self.assertIsNotNone(self.active())

    def test_backup_restore_and_audit(self):
        self.post('rent',self.rent_payload());self.reserve()
        destination=Path(self.temp.name)/'snapshot.db';restored=Path(self.temp.name)/'restored.db'
        copy_database(self.path,destination)
        with self.assertRaises(FileExistsError):copy_database(self.path,destination)
        copy_database(destination,restored,restore=True)
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM mobile_sessions').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM rides').fetchone()[0],1)
        result=audit(restored)
        self.assertEqual(result['integrity'],'ok');self.assertFalse(any(v for k,v in result.items() if k!='integrity'))

    def test_operator_accounts_and_export(self):
        self.assertEqual(self.client.get('/admin/accounts').status_code,200)
        self.client.post('/admin/accounts',data=dict(action='create',student_id='STU006',name='New Student',password='a-unique-test-password'))
        self.assertTrue(self.query("SELECT * FROM students WHERE student_id='STU006'"))
        self.post('rent',self.rent_payload())
        self.client.post('/admin/accounts',data=dict(action='disable',student_id='STU001'))
        self.assertEqual(self.query("SELECT active FROM students WHERE student_id='STU001'")[0]['active'],1)
        response=self.client.get('/admin/export/rides.csv')
        self.assertEqual(response.status_code,200);self.assertIn('CB001',response.text)
        anonymous=self.web.app.test_client()
        self.assertEqual(anonymous.get('/admin/accounts').status_code,302)
        self.assertEqual(anonymous.get('/admin/export/rides.csv').status_code,302)

    def test_production_guard(self):
        with patch.dict(os.environ,{'CAMPUSBIKE_ENV':'production','SECRET_KEY':'short'},clear=True):
            with self.assertRaises(RuntimeError):validate_deployment()
        with patch.dict(os.environ,{'CAMPUSBIKE_ENV':'production','SECRET_KEY':'a'*40,'ADMIN_PASSWORD':'strong-password-for-test','SESSION_COOKIE_SECURE':'1'},clear=True):
            validate_deployment()

    def test_legacy_web_mutations_are_disabled(self):
        with self.client.session_transaction() as session:session['student_id']='STU001'
        # The legacy return handler must not alter or bypass a mobile reservation.
        self.post('rent',self.rent_payload());ride=self.active()
        response=self.client.post('/return/'+str(ride['ride_id']),data={'station_name':'Library'})
        self.assertEqual(response.status_code,409)
        self.assertIsNotNone(self.active())

    def test_competing_students_cannot_reserve_the_same_dock(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        self.post('rent',self.rent_payload())
        other=self.web.app.test_client()
        response=other.post('/api/login',json={'student_id':'STU002','password':'test-password-for-suite'})
        other_token=response.json['access_token']
        other.post('/api/rent',json=self.rent_payload('CB002','STU002'),headers={'Authorization':'Bearer '+other_token})
        self.query("UPDATE slots SET status='Maintenance' WHERE station_id=2 AND slot_number!='SLOT-01'")
        barrier=threading.Barrier(2)
        def reserve(student,token):
            ride=self.query('SELECT ride_id FROM rides WHERE student_id=? AND returned_at IS NULL',(student,))[0]
            payload=self.sample_payload();payload.update(student_id=student,ride_id=ride['ride_id'])
            with self.web.app.test_client() as client:
                barrier.wait(timeout=5)
                return client.post('/api/reserve-return-slot',json=payload,headers={'Authorization':'Bearer '+token}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[pool.submit(reserve,'STU001',self.token),pool.submit(reserve,'STU002',other_token)]
            self.assertEqual(sorted(r.result() for r in results),[200,409])
        self.assertEqual(len(self.query("SELECT * FROM slots WHERE station_id=2 AND status='Reserved'")),1)

    def test_account_post_requires_csrf(self):
        self.web.app.config['WTF_CSRF_ENABLED']=True
        try:
            response=self.client.post('/admin/accounts',data=dict(action='disable',student_id='STU002'))
            self.assertEqual(response.status_code,400)
            self.assertEqual(self.query("SELECT active FROM students WHERE student_id='STU002'")[0]['active'],1)
        finally:
            self.web.app.config['WTF_CSRF_ENABLED']=False

    def test_admin_login_throttle_and_headers(self):
        client=self.web.app.test_client()
        for _ in range(10):
            self.assertEqual(client.post('/admin/login',data={'username':'admin','password':'wrong'}).status_code,200)
        self.assertEqual(client.post('/admin/login',data={'username':'admin','password':'wrong'}).status_code,429)
        self.assertEqual(client.get('/admin/login').headers['Cache-Control'],'no-store')

    def test_malformed_return_ids_do_not_mutate_assignments(self):
        self.post('rent', self.rent_payload())
        assigned = self.reserve()
        before = self.query('SELECT * FROM slots')
        for route in ('reserve-return-slot', 'cancel-return-slot', 'end-ride'):
            for field, value in [('ride_id', True), ('ride_id', 2**80), ('station_id', []), ('station_id', {}), ('slot_number', [])]:
                payload = dict(ride_id=assigned['ride_id'], station_id=2, slot_number=assigned['slot'])
                payload[field] = value
                with self.subTest(route=route, field=field, value=value):
                    self.assertEqual(self.client.post('/api/'+route, json=payload).status_code, 400)
        self.assertEqual(self.query('SELECT * FROM slots'), before)
        self.assertIsNotNone(self.active())

    def test_null_expiry_releases_corrupt_student_assignment(self):
        self.post('rent', self.rent_payload())
        self.reserve()
        self.query("UPDATE slots SET reserved_until=NULL WHERE bike_id='CB001'")
        self.assertNotIn('reserved_return_slot', self.active())
        self.assertFalse(self.query("SELECT * FROM slots WHERE bike_id='CB001' AND status='Reserved'"))
        self.assertIsNotNone(self.active())
