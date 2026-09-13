from flask import Blueprint, jsonify, request
import sqlite3
import os

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

DB_NAME = os.path.join(
    BASE_DIR,
    "campusbike.db"
)


def get_db():

    connection = sqlite3.connect(DB_NAME)

    connection.row_factory = sqlite3.Row

    return connection


def india_time():

    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S")


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


# =========================================================
# DEVELOPER LOGIN
# =========================================================

@mobile_api.route(
    "/dev-login",
    methods=["POST"]
)
def dev_login():

    data = request.get_json(silent=True) or {}

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()


    if not student_id:

        return jsonify({
            "success": False,
            "message": "Student ID is required."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    cursor.execute("""
        SELECT
            student_id,
            name,
            email,
            active
        FROM students
        WHERE student_id = ?
    """, (
        student_id,
    ))


    student = cursor.fetchone()

    connection.close()


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


    return jsonify({

        "success": True,

        "student": {
            "student_id": student["student_id"],
            "name": student["name"],
            "email": student["email"]
        }

    })


# =========================================================
# CAMPUSES
# =========================================================

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


    student_id = str(
        data.get("student_id", "")
    ).strip().upper()


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
                active

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
                active

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


    return jsonify({

        "success": True,

        "bike": {
            "bike_id": bike["bike_id"],
            "status": bike["status"],
            "station": bike["station"],
            "slot": bike["slot"],
            "lock_status": bike["lock_status"]
        }

    })

# =========================================================
# RESERVE STUDENT RETURN DOCK
# =========================================================

@mobile_api.route(
    "/reserve-return-slot",
    methods=["POST"]
)
def reserve_return_slot():

    data = request.get_json(silent=True) or {}

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()

    station_id = data.get("station_id")


    if not student_id:

        return jsonify({
            "success": False,
            "message": "Student ID is missing."
        }), 400


    try:
        station_id = int(station_id)
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid return station."
        }), 400


    connection = get_db()
    cursor = connection.cursor()


    try:

        cursor.execute("BEGIN IMMEDIATE")


        # -------------------------------------------------
        # ACTIVE RIDE + BIKE
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                r.ride_id,
                r.bike_id,
                b.status AS bike_status,
                b.current_user

            FROM rides r

            JOIN bikes b
                ON b.bike_id = r.bike_id

            WHERE
                r.student_id = ?
                AND r.returned_at IS NULL

            ORDER BY r.ride_id DESC

            LIMIT 1
        """, (
            student_id,
        ))


        ride = cursor.fetchone()


        if ride is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "You do not have an active ride."
            }), 409


        if (
            ride["bike_status"] != "In use"
            or ride["current_user"] != student_id
        ):

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "The active bike is not assigned correctly."
            }), 409


        bike_id = ride["bike_id"]


        # -------------------------------------------------
        # EXISTING STUDENT RESERVATION
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                sl.slot_id,
                sl.station_id,
                sl.slot_number,

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

            ORDER BY sl.slot_id

            LIMIT 1
        """, (
            bike_id,
        ))


        existing = cursor.fetchone()


        if existing:

            sponsor_name = (
                str(existing["sponsor_name"]).strip()
                if existing["sponsor_name"]
                else ""
            )

            existing_public = (
                f"{sponsor_name} {existing['display_name']}"
                if sponsor_name
                else existing["display_name"]
            )


            if existing["station_id"] != station_id:

                connection.rollback()

                return jsonify({
                    "success": False,
                    "message":
                        f"You already have {existing['slot_number']} reserved at {existing_public}. Cancel that return assignment before choosing another station.",
                    "reservation": {
                        "bike_id": bike_id,
                        "station_id": existing["station_id"],
                        "station": existing_public,
                        "slot": existing["slot_number"],
                    }
                }), 409


            connection.commit()

            return jsonify({
                "success": True,
                "already_reserved": True,
                "reservation": {
                    "bike_id": bike_id,
                    "station_id": existing["station_id"],
                    "station": existing_public,
                    "slot": existing["slot_number"],
                }
            })


        # -------------------------------------------------
        # RETURN STATION
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                station_id,
                station_name,

                COALESCE(
                    NULLIF(TRIM(display_name), ''),
                    station_name
                ) AS display_name,

                sponsor_name,
                active

            FROM stations

            WHERE station_id = ?
        """, (
            station_id,
        ))


        station = cursor.fetchone()


        if station is None or station["active"] != 1:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "Return station is unavailable."
            }), 409


        sponsor_name = (
            str(station["sponsor_name"]).strip()
            if station["sponsor_name"]
            else ""
        )

        public_station_name = (
            f"{sponsor_name} {station['display_name']}"
            if sponsor_name
            else station["display_name"]
        )


        # -------------------------------------------------
        # FIND + RESERVE EXACT DOCK
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                slot_id,
                slot_number

            FROM slots

            WHERE
                station_id = ?
                AND status = 'Available'
                AND bike_id IS NULL

            ORDER BY slot_number

            LIMIT 1
        """, (
            station_id,
        ))


        slot = cursor.fetchone()


        if slot is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message":
                    f"No return docks are available at {public_station_name}."
            }), 409


        cursor.execute("""
            UPDATE slots

            SET
                bike_id = ?,
                status = 'Reserved'

            WHERE
                slot_id = ?
                AND station_id = ?
                AND status = 'Available'
                AND bike_id IS NULL
        """, (
            bike_id,
            slot["slot_id"],
            station_id,
        ))


        if cursor.rowcount != 1:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "That dock was just taken. Please try again."
            }), 409


        connection.commit()


        return jsonify({
            "success": True,
            "already_reserved": False,
            "reservation": {
                "bike_id": bike_id,
                "station_id": station_id,
                "station": public_station_name,
                "slot": slot["slot_number"],
            }
        })


    except Exception as error:

        connection.rollback()

        print(
            "Reserve return dock error:",
            error
        )

        return jsonify({
            "success": False,
            "message": "Could not reserve a return dock."
        }), 500


    finally:
        connection.close()


# =========================================================
# CANCEL STUDENT RETURN DOCK RESERVATION
# =========================================================

@mobile_api.route(
    "/cancel-return-slot",
    methods=["POST"]
)
def cancel_return_slot():

    data = request.get_json(silent=True) or {}

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()


    if not student_id:

        return jsonify({
            "success": False,
            "message": "Student ID is missing."
        }), 400


    connection = get_db()
    cursor = connection.cursor()


    try:

        cursor.execute("BEGIN IMMEDIATE")


        cursor.execute("""
            SELECT
                r.bike_id,
                b.status AS bike_status,
                b.current_user

            FROM rides r

            JOIN bikes b
                ON b.bike_id = r.bike_id

            WHERE
                r.student_id = ?
                AND r.returned_at IS NULL

            ORDER BY r.ride_id DESC

            LIMIT 1
        """, (
            student_id,
        ))


        ride = cursor.fetchone()


        if ride is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "You do not have an active ride."
            }), 409


        if (
            ride["bike_status"] != "In use"
            or ride["current_user"] != student_id
        ):

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "The active bike is not assigned correctly."
            }), 409


        cursor.execute("""
            SELECT
                slot_id,
                station_id,
                slot_number

            FROM slots

            WHERE
                bike_id = ?
                AND status = 'Reserved'

            ORDER BY slot_id

            LIMIT 1
        """, (
            ride["bike_id"],
        ))


        reservation = cursor.fetchone()


        if reservation is None:

            connection.commit()

            return jsonify({
                "success": True,
                "message": "No return dock reservation was active."
            })


        cursor.execute("""
            UPDATE slots

            SET
                bike_id = NULL,
                status = 'Available'

            WHERE
                slot_id = ?
                AND bike_id = ?
                AND status = 'Reserved'
        """, (
            reservation["slot_id"],
            ride["bike_id"],
        ))


        if cursor.rowcount != 1:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "The return dock reservation changed. Please refresh."
            }), 409


        connection.commit()


        return jsonify({
            "success": True,
            "message": "Return dock reservation cancelled."
        })


    except Exception as error:

        connection.rollback()

        print(
            "Cancel return dock error:",
            error
        )

        return jsonify({
            "success": False,
            "message": "Could not cancel the return dock reservation."
        }), 500


    finally:
        connection.close()


# =========================================================
# END RIDE / RETURN BIKE
# =========================================================

@mobile_api.route(
    "/end-ride",
    methods=["POST"]
)
def end_ride():

    data = request.get_json(silent=True) or {}

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()

    station_id = data.get("station_id")

    requested_slot = str(
        data.get("slot_number", "")
    ).strip().upper()


    if not student_id:

        return jsonify({
            "success": False,
            "message": "Student ID is missing."
        }), 400


    if station_id is None:

        return jsonify({
            "success": False,
            "message": "Return station is required."
        }), 400


    try:

        station_id = int(station_id)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid return station."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    try:

        # -------------------------------------------------
        # LOCK DATABASE FOR RETURN TRANSACTION
        # -------------------------------------------------

        cursor.execute("BEGIN IMMEDIATE")


        # -------------------------------------------------
        # FIND ACTIVE RIDE
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                ride_id,
                bike_id,
                student_id,
                rented_at

            FROM rides

            WHERE student_id = ?
              AND returned_at IS NULL

            ORDER BY ride_id DESC

            LIMIT 1
        """, (
            student_id,
        ))


        ride = cursor.fetchone()


        if ride is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "You do not have an active ride."
            }), 409


        bike_id = ride["bike_id"]


        # -------------------------------------------------
        # VERIFY BIKE
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                bike_id,
                status,
                current_user

            FROM bikes

            WHERE bike_id = ?
        """, (
            bike_id,
        ))


        bike = cursor.fetchone()


        if bike is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "Bike could not be found."
            }), 404


        if bike["current_user"] != student_id:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "This bike is not assigned to this student."
            }), 409


        # -------------------------------------------------
        # VERIFY RETURN STATION
        # -------------------------------------------------

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
                active

            FROM stations

            WHERE station_id = ?
        """, (
            station_id,
        ))


        station = cursor.fetchone()


        if station is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "Return station not found."
            }), 404


        if station["active"] != 1:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "This station is currently unavailable."
            }), 409


        # Legacy internal name.
        # Kept temporarily for old database compatibility.
        internal_station_name = station["station_name"]


        # Public name shown to students.
        display_name = station["display_name"]

        sponsor_name = (
            str(station["sponsor_name"]).strip()
            if station["sponsor_name"]
            else ""
        )


        public_station_name = (
            f"{sponsor_name} {display_name}"
            if sponsor_name
            else display_name
        )


        # -------------------------------------------------
        # USE THE STUDENT'S RESERVED DOCK WHEN PRESENT
        # -------------------------------------------------
        #
        # New mobile flow:
        # GPS check -> reserve exact dock -> student sees
        # Dock 03 -> student docks -> confirm.
        #
        # Old callers are still supported: when no student
        # reservation exists, the backend can atomically
        # take the first free dock as before.
        # -------------------------------------------------

        slot = None


        if requested_slot:

            cursor.execute("""
                SELECT
                    slot_id,
                    slot_number,
                    status,
                    bike_id

                FROM slots

                WHERE
                    station_id = ?
                    AND slot_number = ?
                    AND status = 'Reserved'
                    AND bike_id = ?

                LIMIT 1
            """, (
                station_id,
                requested_slot,
                bike_id,
            ))

            slot = cursor.fetchone()


            if slot is None:

                connection.rollback()

                return jsonify({
                    "success": False,
                    "message":
                        "The assigned return dock is no longer reserved for this bike. Please refresh and request a dock again."
                }), 409


        else:

            # Recover reservation even if an older mobile
            # client omitted slot_number.
            cursor.execute("""
                SELECT
                    slot_id,
                    slot_number,
                    status,
                    bike_id

                FROM slots

                WHERE
                    station_id = ?
                    AND status = 'Reserved'
                    AND bike_id = ?

                ORDER BY slot_id

                LIMIT 1
            """, (
                station_id,
                bike_id,
            ))

            slot = cursor.fetchone()


        if slot is None:

            # If this bike has a reservation at a different
            # station, do not silently leave it stuck there.
            cursor.execute("""
                SELECT
                    sl.station_id,
                    sl.slot_number,

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

                ORDER BY sl.slot_id

                LIMIT 1
            """, (
                bike_id,
            ))

            other_reservation = cursor.fetchone()


            if other_reservation:

                other_sponsor = (
                    str(other_reservation["sponsor_name"]).strip()
                    if other_reservation["sponsor_name"]
                    else ""
                )

                other_name = (
                    f"{other_sponsor} {other_reservation['display_name']}"
                    if other_sponsor
                    else other_reservation["display_name"]
                )

                connection.rollback()

                return jsonify({
                    "success": False,
                    "message":
                        f"This bike already has {other_reservation['slot_number']} reserved at {other_name}."
                }), 409


            # Backward-compatible fallback.
            cursor.execute("""
                SELECT
                    slot_id,
                    slot_number,
                    status,
                    bike_id

                FROM slots

                WHERE
                    station_id = ?
                    AND status = 'Available'
                    AND bike_id IS NULL

                ORDER BY slot_number

                LIMIT 1
            """, (
                station_id,
            ))

            slot = cursor.fetchone()


        if slot is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "message":
                    f"No return slots are available at {public_station_name}."
            }), 409


        return_slot = slot["slot_number"]

        now = india_time()


        # -------------------------------------------------
        # OCCUPY RETURN SLOT
        # -------------------------------------------------

        if slot["status"] == "Reserved":

            cursor.execute("""
                UPDATE slots

                SET
                    status = 'Occupied'

                WHERE
                    slot_id = ?
                    AND station_id = ?
                    AND status = 'Reserved'
                    AND bike_id = ?
            """, (
                slot["slot_id"],
                station_id,
                bike_id,
            ))

        else:

            cursor.execute("""
                UPDATE slots

                SET
                    bike_id = ?,
                    status = 'Occupied'

                WHERE
                    slot_id = ?
                    AND station_id = ?
                    AND status = 'Available'
                    AND bike_id IS NULL
            """, (
                bike_id,
                slot["slot_id"],
                station_id,
            ))


        if cursor.rowcount != 1:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "The assigned dock changed. Please try again."
            }), 409


        # -------------------------------------------------
        # CHECK FOR UNRESOLVED MAINTENANCE REPORT
        # -------------------------------------------------

        cursor.execute("""
            SELECT report_id

            FROM maintenance_reports

            WHERE bike_id = ?
              AND resolved_at IS NULL
              AND status != 'Resolved'

            LIMIT 1
        """, (
            bike_id,
        ))


        unresolved_report = cursor.fetchone()


        return_status = (
            "Maintenance"
            if unresolved_report
            else "Available"
        )


        # -------------------------------------------------
        # UPDATE BIKE
        # -------------------------------------------------
        #
        # station_id is now the permanent relationship.
        #
        # station text remains temporarily so older parts
        # of the app continue working during migration.
        # -------------------------------------------------

        cursor.execute("""
            UPDATE bikes

            SET
                status = ?,
                current_user = NULL,

                station = ?,
                station_id = ?,

                slot = ?,

                lock_status = 'Locked',

                location = ?,

                last_updated = ?,

                total_rides =
                    COALESCE(total_rides, 0) + 1

            WHERE bike_id = ?
        """, (
            return_status,
            internal_station_name,
            station_id,
            return_slot,
            internal_station_name,
            now,
            bike_id,
        ))


        # -------------------------------------------------
        # COMPLETE RIDE
        # -------------------------------------------------
        #
        # return_station is a historical/public snapshot.
        #
        # return_station_id is the permanent relationship.
        # -------------------------------------------------

        cursor.execute("""
            UPDATE rides

            SET
                returned_at = ?,

                return_station = ?,

                return_station_id = ?,

                return_slot = ?

            WHERE ride_id = ?
              AND returned_at IS NULL
        """, (
            now,
            public_station_name,
            station_id,
            return_slot,
            ride["ride_id"],
        ))


        if cursor.rowcount != 1:

            connection.rollback()

            return jsonify({
                "success": False,
                "message": "The ride could not be completed."
            }), 409


        connection.commit()


        return jsonify({

            "success": True,

            "message": "Ride completed successfully.",

            "return": {

                "ride_id":
                    ride["ride_id"],

                "bike_id":
                    bike_id,

                "station_id":
                    station_id,

                "station_code":
                    station["station_code"],

                "station":
                    public_station_name,

                "slot":
                    return_slot,

                "returned_at":
                    now,

                "lock_status":
                    "Locked",

                "bike_status":
                    return_status,

                "maintenance_required":
                    bool(unresolved_report)

            }

        })


    except Exception as error:

        connection.rollback()

        print(
            "End ride API error:",
            error
        )

        return jsonify({
            "success": False,
            "message": "Could not complete the ride."
        }), 500


    finally:

        connection.close()


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

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()

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
