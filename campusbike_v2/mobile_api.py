from flask import Blueprint, jsonify, request, g
import sqlite3
import os
import math
import statistics
import time

from datetime import datetime
from zoneinfo import ZoneInfo


mobile_api = Blueprint(
    "mobile_api",
    __name__,
    url_prefix="/api"
)


# =========================================================
# DATABASE
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from settings import DB_NAME


def get_db():

    connection = sqlite3.connect(DB_NAME)

    connection.row_factory = sqlite3.Row

    return connection


def india_time():

    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S")


def verify_rent_location(data, station, db):
    samples = data.get("location_samples")
    if not isinstance(samples, list) or not 3 <= len(samples) <= 6:
        raise ValueError("Refresh the app and take three GPS samples near the bike station.")
    if station["latitude"] is None or station["longitude"] is None:
        raise ValueError("This station needs GPS coordinates configured by the administrator.")

    usable = []
    now = time.time() * 1000

    def distance_m(lat1, lon1, lat2, lon2):
        p1, p2 = map(math.radians, (lat1, lat2))
        a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
        return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, a))))

    for sample in samples:
        try:
            lat, lon, accuracy, timestamp = [sample[k] for k in ("latitude","longitude","accuracy","timestamp")]
            if any(isinstance(v, bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (lat,lon,accuracy,timestamp)):
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= accuracy <= 100 and -10000 <= now-timestamp <= 60000):
                continue
            usable.append((distance_m(lat,lon,station["latitude"],station["longitude"]),accuracy,lat,lon))
        except (KeyError,TypeError):
            continue

    if len(usable) < 2:
        raise ValueError("GPS readings are weak or old. Move into an open area near the bike station and try again.")

    median_distance = statistics.median(x[0] for x in usable)
    allowed_distance = 100 + min(30, min(x[1] for x in usable))
    if median_distance > allowed_distance:
        raise ValueError("You are too far from the bike station. Move closer to rent this bike.")

    boundary = db.execute(
        "SELECT latitude,longitude FROM campus_boundary_points WHERE campus_id=? ORDER BY point_order",
        (station["campus_id"],)
    ).fetchall()
    if len(boundary) >= 3:
        inside_count = 0
        for sample in usable:
            lat, lon = sample[2], sample[3]
            inside = False
            previous = boundary[-1]
            for point in boundary:
                x1,y1 = previous["longitude"],previous["latitude"]
                x2,y2 = point["longitude"],point["latitude"]
                if (y1>lat)!=(y2>lat) and lon < (x2-x1)*(lat-y1)/(y2-y1)+x1:
                    inside = not inside
                previous = point
            inside_count += int(inside)
        if inside_count <= len(usable)//2:
            raise ValueError("Your GPS position is outside the campus service area.")

def parse_mobile_qr_token(raw_value):

    value = str(
        raw_value or ""
    ).strip()


    # New official CampusBike QR format:
    #
    # CAMPUSBIKE|CB001|secret
    #
    parts = value.split("|")


    if (
        len(parts) == 3
        and parts[0].strip().upper() == "CAMPUSBIKE"
    ):

        bike_id = parts[1].strip().upper()

        qr_secret = parts[2].strip()

        return bike_id, qr_secret


    # Legacy development QR format:
    #
    # secret only
    #
    return None, value


# =========================================================
# HEALTH
# =========================================================

@mobile_api.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "service": "CampusBike Mobile API"
    })


@mobile_api.route("/campuses")
def get_campuses():

    connection = get_db()

    cursor = connection.cursor()


    cursor.execute("""
        SELECT
            campus_id,
            campus_name,
            city,
            latitude,
            longitude,
            active
        FROM campuses
        WHERE active = 1
        ORDER BY campus_name
    """)


    rows = cursor.fetchall()

    connection.close()


    return jsonify([
        dict(row)
        for row in rows
    ])


# =========================================================
# STATIONS
# =========================================================

@mobile_api.route("/stations")
def get_stations():

    connection = get_db()

    cursor = connection.cursor()


    cursor.execute("""
        SELECT
            station_id,
            station_code,
            station_name,

            COALESCE(
                NULLIF(TRIM(display_name), ''),
                station_name
            ) AS display_name,

            sponsor_name,
            total_slots,
            active,
            campus_id,
            latitude,
            longitude

        FROM stations

        WHERE active = 1

        ORDER BY station_id
    """)


    station_rows = cursor.fetchall()

    stations = []


    for station in station_rows:

        # Internal legacy name.
        # This is still used temporarily while the rest
        # of rent/return is migrated to station_id.
        internal_station_name = station["station_name"]


        # -------------------------------------------------
        # PUBLIC NAME
        # -------------------------------------------------

        display_name = station["display_name"]

        sponsor_name = (
            str(station["sponsor_name"]).strip()
            if station["sponsor_name"]
            else ""
        )


        public_name = (
            f"{sponsor_name} {display_name}"
            if sponsor_name
            else display_name
        )


        # -------------------------------------------------
        # AVAILABLE BIKES
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                bike_id,
                status,
                slot,
                lock_status

            FROM bikes

            WHERE station = ?
              AND status = 'Available'
              AND active = 1

            ORDER BY bike_id
        """, (
            internal_station_name,
        ))


        bike_rows = cursor.fetchall()


        bikes = [
            dict(row)
            for row in bike_rows
        ]


        # -------------------------------------------------
        # AVAILABLE SLOTS
        # -------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)

            FROM slots

            WHERE station_name = ?
              AND status = 'Available'
        """, (
            internal_station_name,
        ))


        available_slots = cursor.fetchone()[0]


        stations.append({

            "station_id":
                station["station_id"],

            "station_code":
                station["station_code"],

            # Keep this key for the current mobile app.
            # It now contains the PUBLIC name.
            "station_name":
                public_name,

            "display_name":
                display_name,

            "sponsor_name":
                sponsor_name or None,

            "campus_id":
                station["campus_id"],

            "latitude":
                station["latitude"],

            "longitude":
                station["longitude"],

            "total_slots":
                station["total_slots"],

            "available_slots":
                available_slots,

            "available_bikes":
                len(bikes),

            "bikes":
                bikes

        })


    connection.close()

    return jsonify(stations)


# =========================================================
# ACTIVE RIDE
# =========================================================

@mobile_api.route(
    "/students/<student_id>/active-ride",
    methods=["GET"]
)
def get_active_ride(student_id):

    student_id = student_id.strip().upper()


    connection = get_db()

    cursor = connection.cursor()


    cursor.execute("""
        SELECT
            student_id,
            name,
            active
        FROM students
        WHERE student_id = ?
    """, (
        student_id,
    ))


    student = cursor.fetchone()


    if student is None:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404


    cursor.execute("""
        SELECT
            r.ride_id,
            r.bike_id,
            r.student_id,
            r.rented_at,
            r.start_station,
            r.start_slot,
            r.rent_method,
            r.qr_verified,

            b.status AS bike_status,
            b.lock_status,
            b.current_user

        FROM rides r

        LEFT JOIN bikes b
            ON b.bike_id = r.bike_id

        WHERE r.student_id = ?
          AND r.returned_at IS NULL

        ORDER BY r.ride_id DESC

        LIMIT 1
    """, (
        student_id,
    ))


    ride = cursor.fetchone()


    if ride is None:

        connection.close()

        return jsonify({
            "success": True,
            "active_ride": None
        })


    # -----------------------------------------------------
    # RECOVER ANY PENDING STUDENT RETURN DOCK RESERVATION
    # -----------------------------------------------------
    #
    # This lets the app recover correctly after a refresh
    # or restart while the student is walking the bike into
    # the assigned dock.
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            sl.station_id,
            sl.slot_number,
            sl.reserved_until,

            COALESCE(
                NULLIF(TRIM(s.display_name), ''),
                s.station_name
            ) AS display_name,

            s.sponsor_name

        FROM slots sl

        JOIN stations s
            ON s.station_id = sl.station_id

        WHERE
            sl.bike_id = ?
            AND sl.status = 'Reserved'
            AND s.active = 1

        ORDER BY sl.slot_id

        LIMIT 1
    """, (
        ride["bike_id"],
    ))


    reservation = cursor.fetchone()

    active_ride = dict(ride)


    if reservation:

        sponsor_name = (
            str(reservation["sponsor_name"]).strip()
            if reservation["sponsor_name"]
            else ""
        )

        public_name = (
            f"{sponsor_name} {reservation['display_name']}"
            if sponsor_name
            else reservation["display_name"]
        )

        active_ride.update({
            "reserved_return_station_id":
                reservation["station_id"],

            "reserved_return_station":
                public_name,

            "reserved_return_slot":
                reservation["slot_number"],
            "reserved_return_expires_at": reservation["reserved_until"],
        })


    connection.close()


    return jsonify({
        "success": True,
        "active_ride": active_ride
    })


# =========================================================
# RENT BIKE USING QR
# =========================================================

@mobile_api.route(
    "/rent",
    methods=["POST"]
)
def rent_bike():

    data = request.get_json(silent=True) or {}


    student_id = g.student_id


    bike_id = str(
        data.get("bike_id", "")
    ).strip().upper()


    qr_token = str(
        data.get("qr_token", "")
    ).strip()


    # -----------------------------------------------------
    # REQUIRED DATA
    # -----------------------------------------------------

    if not student_id:

        return jsonify({
            "success": False,
            "message": "Student ID is missing."
        }), 400


    if not bike_id:

        return jsonify({
            "success": False,
            "message": "Bike ID is missing."
        }), 400


    if not qr_token:

        return jsonify({
            "success": False,
            "message": "QR code is missing."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    try:

        # =================================================
        # Serialize the active-ride check and rental writes together.
        # Two simultaneous requests must not rent two bikes to one student.
        cursor.execute("BEGIN IMMEDIATE")

        # VERIFY STUDENT
        # =================================================

        cursor.execute("""
            SELECT
                student_id,
                active
            FROM students
            WHERE student_id = ?
        """, (
            student_id,
        ))


        student = cursor.fetchone()


        if student is None:

            return jsonify({
                "success": False,
                "message": "Student not found."
            }), 404


        if student["active"] != 1:

            return jsonify({
                "success": False,
                "message": "Student account is inactive."
            }), 403


        # =================================================
        # STUDENT MUST NOT ALREADY HAVE ACTIVE RIDE
        # =================================================

        cursor.execute("""
            SELECT
                ride_id,
                bike_id
            FROM rides
            WHERE student_id = ?
              AND returned_at IS NULL
            ORDER BY ride_id DESC
            LIMIT 1
        """, (
            student_id,
        ))


        current_ride = cursor.fetchone()


        if current_ride is not None:

            return jsonify({

                "success": False,

                "message":
                    f"You already have {current_ride['bike_id']} rented."

            }), 409


        # =================================================
        # VERIFY BIKE
        # =================================================

        cursor.execute("""
            SELECT
                bike_id,
                status,
                current_user,
                station,
                station_id,
                slot,
                lock_status,
                qr_secret,
                active
            FROM bikes
            WHERE bike_id = ?
        """, (
            bike_id,
        ))


        bike = cursor.fetchone()


        if bike is None:

            return jsonify({
                "success": False,
                "message": "Bike not found."
            }), 404


        if bike["active"] != 1:

            return jsonify({
                "success": False,
                "message": "This bike is not active."
            }), 409


        if bike["status"] != "Available":

            return jsonify({
                "success": False,
                "message": f"{bike_id} is not available."
            }), 409


        # =================================================
        # VERIFY QR BELONGS TO SELECTED BIKE
        # =================================================

        qr_bike_id, qr_secret = parse_mobile_qr_token(
            qr_token
        )


        # If the QR itself contains a bike ID,
        # it must match the bike selected by the student.
        if (
            qr_bike_id
            and qr_bike_id != bike_id
        ):

            return jsonify({

                "success": False,

                "message":
                    f"This QR code belongs to {qr_bike_id}, not {bike_id}."

            }), 400


        # Verify secret stored in database.
        if bike["qr_secret"] != qr_secret:

            return jsonify({

                "success": False,

                "message":
                    f"This QR code does not belong to {bike_id}."

            }), 400


        start_station_id = bike["station_id"]

        start_slot = bike["slot"]


        if not start_station_id or not start_slot:

            return jsonify({

                "success": False,

                "message":
                    "Bike is not correctly docked at a station."

            }), 409


        # =================================================
        # GET PUBLIC STATION NAME
        # =================================================

        cursor.execute("""
            SELECT
                station_id,
                station_name,

                COALESCE(
                    NULLIF(TRIM(display_name), ''),
                    station_name
                ) AS display_name,

                sponsor_name,
                active,
                latitude,
                longitude,
                campus_id

            FROM stations

            WHERE station_id = ?
        """, (
            start_station_id,
        ))


        start_station_row = cursor.fetchone()


        if (
            start_station_row is None
            or start_station_row["active"] != 1
        ):

            return jsonify({

                "success": False,

                "message":
                    "The bike's station is not currently available."

            }), 409


        try:
            verify_rent_location(data, start_station_row, connection)
        except ValueError as error:
            return jsonify({"success": False, "message": str(error)}), 403


        display_name = start_station_row["display_name"]

        sponsor_name = (
            str(start_station_row["sponsor_name"]).strip()
            if start_station_row["sponsor_name"]
            else ""
        )


        start_station = (
            f"{sponsor_name} {display_name}"
            if sponsor_name
            else display_name
        )


        # =================================================
        # REMOVE BIKE FROM DOCK
        # =================================================

        cursor.execute("""
            UPDATE slots

            SET
                bike_id = NULL,
                status = 'Available'

            WHERE station_id = ?
              AND slot_number = ?
              AND bike_id = ?
        """, (
            start_station_id,
            start_slot,
            bike_id,
        ))


        if cursor.rowcount != 1:

            return jsonify({

                "success": False,

                "message":
                    "The bike dock could not be verified."

            }), 409


        # =================================================
        # UPDATE BIKE
        # =================================================

        now = india_time()


        cursor.execute("""
            UPDATE bikes

            SET
                status = 'In use',
                current_user = ?,
                station = NULL,
                station_id = NULL,
                slot = NULL,
                lock_status = 'Unlocked',
                location = 'On Ride',
                last_updated = ?

            WHERE bike_id = ?
        """, (
            student_id,
            now,
            bike_id,
        ))


        # =================================================
        # CREATE RIDE
        # =================================================

        cursor.execute("""
            INSERT INTO rides (
                bike_id,
                student_id,
                rented_at,
                returned_at,
                return_station,
                return_slot,
                start_station,
                start_station_id,
                start_slot,
                rent_method,
                qr_verified
            )

            VALUES (
                ?,
                ?,
                ?,
                NULL,
                NULL,
                NULL,
                ?,
                ?,
                ?,
                ?,
                1
            )
        """, (
            bike_id,
            student_id,
            now,
            start_station,
            start_station_id,
            start_slot,
            "mobile_qr",
        ))


        ride_id = cursor.lastrowid


        connection.commit()


        return jsonify({

            "success": True,

            "message":
                f"{bike_id} rented successfully.",

            "ride": {

                "ride_id":
                    ride_id,

                "bike_id":
                    bike_id,

                "student_id":
                    student_id,

                "rented_at":
                    now,

                "start_station":
                    start_station,

                "start_slot":
                    start_slot,

                "qr_verified":
                    1

            }

        })


    except Exception as error:

        connection.rollback()


        print(
            "Rent API error:",
            error
        )


        return jsonify({

            "success": False,

            "message":
                "Could not start the ride."

        }), 500


    finally:

        connection.close()

        # =========================================================
# IDENTIFY BIKE FROM QR
# Used by the red "Scan a bike" button
# =========================================================

@mobile_api.route(
    "/bike-by-qr",
    methods=["POST"]
)
def bike_by_qr():

    data = request.get_json(silent=True) or {}

    qr_token = str(
        data.get("qr_token", "")
    ).strip()


    if not qr_token:

        return jsonify({
            "success": False,
            "message": "QR code is missing."
        }), 400


    qr_bike_id, qr_secret = parse_mobile_qr_token(
        qr_token
    )


    connection = get_db()

    cursor = connection.cursor()


    if qr_bike_id:

        cursor.execute("""
            SELECT
                bike_id,
                status,
                station,
                slot,
                lock_status,
                active,
                station_id

            FROM bikes

            WHERE bike_id = ?
              AND qr_secret = ?

            LIMIT 1
        """, (
            qr_bike_id,
            qr_secret,
        ))

    else:

        cursor.execute("""
            SELECT
                bike_id,
                status,
                station,
                slot,
                lock_status,
                active

            FROM bikes

            WHERE qr_secret = ?

            LIMIT 1
        """, (
            qr_secret,
        ))


    bike = cursor.fetchone()

    connection.close()


    if bike is None:

        return jsonify({
            "success": False,
            "message": "This is not a valid CampusBike QR code."
        }), 404


    if bike["active"] != 1:

        return jsonify({
            "success": False,
            "message": "This bike is currently disabled."
        }), 409


    # Reporting identifies an active bike without requiring it to be rentable.
    # The rental endpoint still independently enforces availability and QR proof.
    if data.get("purpose") == "report":
        return jsonify({"success": True, "bike": {"bike_id": bike["bike_id"]}})

    if bike["status"] != "Available":

        return jsonify({
            "success": False,
            "message": f"{bike['bike_id']} is currently not available."
        }), 409


    if not bike["station"] or not bike["slot"]:

        return jsonify({
            "success": False,
            "message": "This bike is not properly docked."
        }), 409


    connection = get_db()
    station = connection.execute(
        "SELECT latitude,longitude FROM stations WHERE station_id=? AND active=1",
        (bike["station_id"],)
    ).fetchone()
    connection.close()

    if not station or station["latitude"] is None or station["longitude"] is None:
        return jsonify({"success": False, "message": "This station does not have GPS coordinates configured."}), 409

    return jsonify({
        "success": True,
        "bike": {
            "bike_id": bike["bike_id"],
            "status": bike["status"],
            "station": bike["station"],
            "slot": bike["slot"],
            "lock_status": bike["lock_status"],
            "station_latitude": station["latitude"],
            "station_longitude": station["longitude"]
        }
    })

# =========================================================
# STUDENT RIDE HISTORY
# =========================================================

@mobile_api.route(
    "/students/<student_id>/rides",
    methods=["GET"]
)
def student_ride_history(student_id):

    student_id = student_id.strip().upper()

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            ride_id,
            bike_id,
            student_id,
            rented_at,
            returned_at,
            start_station,
            start_slot,
            return_station,
            return_slot,
            rent_method,
            qr_verified
        FROM rides
        WHERE student_id = ?
          AND returned_at IS NOT NULL
        ORDER BY ride_id DESC
    """, (
        student_id,
    ))

    rides = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return jsonify({
        "success": True,
        "rides": rides,
        "total_rides": len(rides)
    })

# =========================================================
# MAINTENANCE / REPORT A PROBLEM
# =========================================================

@mobile_api.route("/maintenance-reports", methods=["POST"])
def create_maintenance_report():

    from flask import request
    from datetime import datetime
    from zoneinfo import ZoneInfo

    data = request.get_json(silent=True) or {}

    student_id = g.student_id

    bike_id = str(
        data.get("bike_id", "")
    ).strip().upper()

    issue_type = str(
        data.get("issue_type", "")
    ).strip()

    description = str(
        data.get("description", "")
    ).strip()

    severity = str(
        data.get("severity", "Medium")
    ).strip().title()


    # -----------------------------------------------------
    # VALID ISSUE TYPES
    # -----------------------------------------------------

    issue_types = {
        "brake": "Brake",
        "tyre": "Tyre",
        "chain": "Chain",
        "seat": "Seat",
        "lock/dock": "Lock/Dock",
        "qr code": "QR Code",
        "other": "Other",
    }


    normalized_issue = issue_types.get(
        issue_type.lower()
    )


    if not student_id:

        return jsonify({
            "success": False,
            "message": "Student ID is required."
        }), 400


    if not bike_id:

        return jsonify({
            "success": False,
            "message": "Bike ID is required."
        }), 400


    if not normalized_issue:

        return jsonify({
            "success": False,
            "message": "Choose a valid issue type."
        }), 400


    if severity not in {
        "Low",
        "Medium",
        "High"
    }:

        severity = "Medium"


    if len(description) > 500:

        return jsonify({
            "success": False,
            "message": "Description is too long."
        }), 400


    reported_at = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    connection = get_db()


    try:

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        # -------------------------------------------------
        # VERIFY STUDENT
        # -------------------------------------------------

        student = connection.execute(
            """
            SELECT
                student_id,
                active

            FROM students

            WHERE student_id = ?
            """,
            (
                student_id,
            ),
        ).fetchone()


        if not student:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "Student account not found."
            }), 404


        if student["active"] == 0:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "Student account is inactive."
            }), 403


        # -------------------------------------------------
        # VERIFY BIKE
        # -------------------------------------------------

        bike = connection.execute(
            """
            SELECT
                bike_id,
                status,
                station,
                slot,
                active

            FROM bikes

            WHERE bike_id = ?
            """,
            (
                bike_id,
            ),
        ).fetchone()


        if not bike:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "Bike not found."
            }), 404


        if bike["active"] == 0:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "This bike is inactive."
            }), 400


        # -------------------------------------------------
        # CREATE REPORT
        # -------------------------------------------------

        cursor = connection.execute(
            """
            INSERT INTO maintenance_reports (

                bike_id,
                student_id,
                issue_type,
                description,
                status,
                severity,
                reported_at,
                resolved_at

            )

            VALUES (
                ?,
                ?,
                ?,
                ?,
                'Reported',
                ?,
                ?,
                NULL
            )
            """,
            (
                bike_id,
                student_id,
                normalized_issue,
                description,
                severity,
                reported_at,
            ),
        )


        report_id = cursor.lastrowid


        # -------------------------------------------------
        # AVAILABLE BIKE → MAINTENANCE
        # -------------------------------------------------
        #
        # Keep its dock/slot occupied because the bike is
        # still physically parked there.
        #
        # It will disappear from the available-bike list.
        # -------------------------------------------------

        new_bike_status = bike["status"]


        if bike["status"] == "Available":

            connection.execute(
                """
                UPDATE bikes

                SET
                    status = 'Maintenance',
                    current_user = NULL,
                    lock_status = 'Locked',
                    last_updated = ?

                WHERE bike_id = ?
                """,
                (
                    reported_at,
                    bike_id,
                ),
            )


            new_bike_status = "Maintenance"


        connection.commit()


        return jsonify({

            "success": True,

            "message": "Problem reported successfully.",

            "report": {

                "report_id": report_id,

                "bike_id": bike_id,

                "student_id": student_id,

                "issue_type": normalized_issue,

                "description": description,

                "severity": severity,

                "status": "Reported",

                "reported_at": reported_at,

            },

            "bike_status": new_bike_status,

        }), 201


    except sqlite3.Error as error:

        connection.rollback()

        print(
            "Maintenance report database error:",
            error
        )


        return jsonify({
            "success": False,
            "message": "Could not save the report."
        }), 500


    finally:

        connection.close()


from mobile_auth import register_mobile_auth

register_mobile_auth(mobile_api, get_db)

from ride_returns import register_returns
register_returns(mobile_api, get_db, india_time)
