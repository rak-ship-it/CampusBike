"""Atomic exact-dock returns for the software MVP (physical locks are simulated)."""
import json
import math
import os
import statistics
import time
from contextlib import closing
from flask import g, jsonify, request
from return_validation import validate_return_identifiers

RESERVATION_SECONDS = 600


class ReturnError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def expire_reservations(db):
    """Only student assignments expire; admin movement reservations do not."""
    db.execute('''UPDATE slots SET bike_id=NULL, status='Available',
        return_ride_id=NULL, reserved_until=NULL
        WHERE status='Reserved' AND return_ride_id IS NOT NULL AND (
          reserved_until IS NULL OR reserved_until <= ? OR NOT EXISTS (
            SELECT 1 FROM rides r JOIN bikes b ON b.bike_id=r.bike_id
            WHERE r.ride_id=slots.return_ride_id AND r.returned_at IS NULL
              AND r.bike_id=slots.bike_id AND b.status='In use'
          ) OR NOT EXISTS (SELECT 1 FROM stations s WHERE s.station_id=slots.station_id AND s.active=1)
        )''', (int(time.time()),))


def distance_m(lat1, lon1, lat2, lon2):
    p1,p2=map(math.radians,(lat1,lat2))
    a=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,max(0,a))))


def inside_polygon(lat, lon, points):
    inside=False
    previous=points[-1]
    for point in points:
        x1,y1=previous['longitude'],previous['latitude']
        x2,y2=point['longitude'],point['latitude']
        if (y1>lat)!=(y2>lat) and lon < (x2-x1)*(lat-y1)/(y2-y1)+x1:
            inside=not inside
        previous=point
    return inside


def verify_location(data, station, db):
    samples=data.get('location_samples')
    if not isinstance(samples,list) or not 3 <= len(samples) <= 6:
        raise ReturnError('Refresh the app and take three GPS samples near the station.',400)
    if station['latitude'] is None or station['longitude'] is None:
        raise ReturnError('This station needs GPS coordinates configured by the administrator.')
    usable=[]
    now=time.time()*1000
    for sample in samples:
        try:
            values=[sample[k] for k in ('latitude','longitude','accuracy','timestamp')]
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
                continue
            lat,lon,accuracy,timestamp=values
            if not (-90<=lat<=90 and -180<=lon<=180 and 0<=accuracy<=100 and -10000<=now-timestamp<=60000):
                continue
            usable.append((distance_m(lat,lon,station['latitude'],station['longitude']), accuracy,lat,lon))
        except (KeyError,TypeError):
            continue
    if len(usable)<2:
        raise ReturnError('GPS readings are weak or old. Move into an open area and try again.',400)
    median=statistics.median(s[0] for s in usable)
    if median > 100+min(30,min(s[1] for s in usable)):
        raise ReturnError('You are too far from the selected station.',403)
    boundary=db.execute('SELECT latitude,longitude FROM campus_boundary_points WHERE campus_id=? ORDER BY point_order', (station['campus_id'],)).fetchall()
    if len(boundary)>=3 and sum(inside_polygon(s[2],s[3],boundary) for s in usable) <= len(usable)//2:
        raise ReturnError('Your GPS position is outside the campus service area.',403)


def public_name(station):
    name=(station['display_name'] or '').strip() or station['station_name']
    sponsor=(station['sponsor_name'] or '').strip()
    return f'{sponsor} {name}' if sponsor else name


def register_returns(api, get_db, india_time):
    def transaction(action):
        data = request.get_json(silent=True)
        try:
            validate_return_identifiers(data)
        except ValueError as error:
            return jsonify(success=False, message=str(error)), 400
        with closing(get_db()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                expire_reservations(db)
                # Persist expiry even if the subsequent user action is rejected.
                db.commit()
                db.execute('BEGIN IMMEDIATE')
                result=action(db,data)
                db.commit()
                return jsonify(result)
            except ReturnError as error:
                db.rollback()
                return jsonify(success=False,message=str(error)),error.status
            except Exception:
                db.rollback()
                raise

    def ride_for(db, data):
        ride=db.execute('''SELECT r.*,b.status AS bike_status,b.current_user FROM rides r
            JOIN bikes b ON b.bike_id=r.bike_id
            WHERE r.student_id=? AND r.returned_at IS NULL ORDER BY r.ride_id DESC LIMIT 1''',(g.student_id,)).fetchone()
        if not ride or ride['bike_status']!='In use' or ride['current_user']!=g.student_id:
            raise ReturnError('No correctly assigned active ride was found.')
        if data.get('ride_id') != ride['ride_id']:
            raise ReturnError('The ride changed. Refresh My Ride before continuing.')
        return ride

    def reservation_value(slot, station, bike_id):
        return dict(bike_id=bike_id,ride_id=slot['return_ride_id'],station_id=slot['station_id'],
                    station=public_name(station),slot=slot['slot_number'],expires_at=slot['reserved_until'])

    @api.route('/reserve-return-slot',methods=['POST'])
    def reserve_return_slot():
        def action(db,data):
            ride=ride_for(db,data)
            station=db.execute('SELECT * FROM stations WHERE station_id=? AND active=1',(data.get('station_id'),)).fetchone()
            if not station:
                raise ReturnError('Return station is unavailable.')
            source=db.execute('SELECT campus_id FROM stations WHERE station_id=?',(ride['start_station_id'],)).fetchone()
            if not source or source['campus_id'] != station['campus_id']:
                raise ReturnError('Return the bike within its starting campus.',403)
            existing=db.execute("SELECT * FROM slots WHERE bike_id=? AND status='Reserved'",(ride['bike_id'],)).fetchone()
            if existing:
                if existing['station_id']!=station['station_id'] or existing['return_ride_id']!=ride['ride_id']:
                    raise ReturnError('Cancel the current dock assignment before choosing another station.')
                return dict(success=True,already_reserved=True,reservation=reservation_value(existing,station,ride['bike_id']))
            verify_location(data,station,db)
            slot=db.execute("SELECT * FROM slots WHERE station_id=? AND status='Available' AND bike_id IS NULL ORDER BY slot_number LIMIT 1",(station['station_id'],)).fetchone()
            if not slot:
                raise ReturnError('No open docks at this station. Choose another station.')
            until=int(time.time())+RESERVATION_SECONDS
            db.execute("UPDATE slots SET status='Reserved',bike_id=?,return_ride_id=?,reserved_until=? WHERE slot_id=?",(ride['bike_id'],ride['ride_id'],until,slot['slot_id']))
            slot=db.execute('SELECT * FROM slots WHERE slot_id=?',(slot['slot_id'],)).fetchone()
            return dict(success=True,already_reserved=False,reservation=reservation_value(slot,station,ride['bike_id']))
        return transaction(action)

    @api.route('/cancel-return-slot',methods=['POST'])
    def cancel_return_slot():
        def action(db,data):
            ride=ride_for(db,data)
            db.execute("UPDATE slots SET status='Available',bike_id=NULL,return_ride_id=NULL,reserved_until=NULL WHERE return_ride_id=? AND status='Reserved'",(ride['ride_id'],))
            return dict(success=True,message='Dock assignment cancelled. Your ride is still active.')
        return transaction(action)

    @api.route('/end-ride',methods=['POST'])
    def end_ride():
        def action(db,data):
            if os.environ.get('CAMPUSBIKE_SIMULATED_DOCKS','1')!='1':
                raise ReturnError('Physical dock integration is not configured. Contact the operator.',503)
            receipt=db.execute('SELECT * FROM mobile_return_receipts WHERE ride_id=? AND student_id=?',(data.get('ride_id'),g.student_id)).fetchone()
            if receipt:
                if data.get('station_id')!=receipt['station_id'] or data.get('slot_number')!=receipt['slot_number']:
                    raise ReturnError('This ride was already returned to a different dock.')
                return json.loads(receipt['response_json'])
            ride=ride_for(db,data)
            slot=db.execute("SELECT * FROM slots WHERE return_ride_id=? AND status='Reserved' AND bike_id=? AND station_id=? AND slot_number=? AND reserved_until>?",(ride['ride_id'],ride['bike_id'],data.get('station_id'),data.get('slot_number'),int(time.time()))).fetchone()
            if not slot:
                raise ReturnError('Your dock assignment expired or changed. Request a new dock in My Ride.')
            station=db.execute('SELECT * FROM stations WHERE station_id=? AND active=1',(slot['station_id'],)).fetchone()
            if not station:
                raise ReturnError('This station is unavailable. Cancel the assignment and choose another.')
            maintenance=db.execute("SELECT report_id FROM maintenance_reports WHERE bike_id=? AND resolved_at IS NULL AND status!='Resolved' LIMIT 1",(ride['bike_id'],)).fetchone()
            status='Maintenance' if maintenance else 'Available'
            now=india_time()
            db.execute("UPDATE slots SET status='Occupied',return_ride_id=NULL,reserved_until=NULL WHERE slot_id=?",(slot['slot_id'],))
            db.execute("""UPDATE bikes SET status=?,current_user=NULL,station=?,station_id=?,slot=?,lock_status='Locked',location=?,last_updated=?,total_rides=COALESCE(total_rides,0)+1 WHERE bike_id=?""",(status,station['station_name'],station['station_id'],slot['slot_number'],station['station_name'],now,ride['bike_id']))
            db.execute('UPDATE rides SET returned_at=?,return_station=?,return_station_id=?,return_slot=? WHERE ride_id=? AND returned_at IS NULL',(now,public_name(station),station['station_id'],slot['slot_number'],ride['ride_id']))
            result={'success':True,'return':dict(ride_id=ride['ride_id'],bike_id=ride['bike_id'],station_id=station['station_id'],station_code=station['station_code'],station=public_name(station),slot=slot['slot_number'],returned_at=now,lock_status='Locked',bike_status=status,maintenance_required=bool(maintenance),confirmation='simulated')}
            db.execute('INSERT INTO mobile_return_receipts VALUES (?,?,?,?,?)',(ride['ride_id'],g.student_id,station['station_id'],slot['slot_number'],json.dumps(result)))
            return result
        return transaction(action)
