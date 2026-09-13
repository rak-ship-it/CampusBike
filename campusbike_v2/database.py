import os
import secrets
import sqlite3

from datetime import datetime
from zoneinfo import ZoneInfo


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_NAME = os.path.join(
    BASE_DIR,
    "campusbike.db"
)


# =========================================================
# DEFAULT CAMPUSBIKE DATA
# =========================================================

ACTIVE_STATIONS = [
    "Main Gate",
    "Library",
    "Hostel",
    "Canteen",
    "Mechanical Block",
]


# These are ONLY the starting locations for a new/unplaced bike.
# They must NOT be used to reset bike positions after every restart.

DEFAULT_BIKES = {
    "CB001": "Main Gate",
    "CB002": "Library",
    "CB003": "Hostel",
    "CB004": "Canteen",
    "CB005": "Mechanical Block",
}


DEFAULT_STUDENTS = {
    "STU001": "Rahul",
    "STU002": "Arjun",
    "STU003": "Sameer",
    "STU004": "Student 004",
    "STU005": "Student 005",
}


# =========================================================
# TIME
# =========================================================

def india_time():

    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =========================================================
# DATABASE MIGRATION HELPER
# =========================================================

def add_column_if_missing(
    cursor,
    table_name,
    column_name,
    column_definition
):

    columns = cursor.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    existing_columns = {
        row[1]
        for row in columns
    }

    if column_name not in existing_columns:

        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}
            """
        )


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database(
    db_name=DB_NAME
):

    connection = sqlite3.connect(
        db_name
    )

    cursor = connection.cursor()


    try:

        # =================================================
        # CORE TABLES
        # =================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (

                student_id TEXT PRIMARY KEY,

                name TEXT

            )
            """
        )


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bikes (

                bike_id TEXT PRIMARY KEY,

                status TEXT,

                current_user TEXT,

                total_rides INTEGER DEFAULT 0

            )
            """
        )


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rides (

                ride_id INTEGER PRIMARY KEY AUTOINCREMENT,

                bike_id TEXT,

                student_id TEXT,

                rented_at TEXT,

                returned_at TEXT

            )
            """
        )


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS maintenance_reports (

                report_id INTEGER PRIMARY KEY AUTOINCREMENT,

                bike_id TEXT NOT NULL,

                student_id TEXT,

                issue_type TEXT NOT NULL,

                description TEXT,

                status TEXT DEFAULT 'Reported',

                severity TEXT DEFAULT 'Medium',

                reported_at TEXT NOT NULL,

                resolved_at TEXT

            )
            """
        )


        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_maintenance_bike_status
            ON maintenance_reports (bike_id, status)
            """
        )


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stations (

                station_id INTEGER PRIMARY KEY AUTOINCREMENT,

                station_name TEXT UNIQUE,

                display_name TEXT,

                sponsor_name TEXT,

                total_slots INTEGER DEFAULT 4

            )
            """
        )


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS slots (

                slot_id INTEGER PRIMARY KEY AUTOINCREMENT,

                station_name TEXT,

                slot_number TEXT,

                bike_id TEXT,

                status TEXT

            )
            """
        )


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS campuses (

                campus_id INTEGER PRIMARY KEY AUTOINCREMENT,

                campus_name TEXT UNIQUE NOT NULL,

                city TEXT,

                latitude REAL,

                longitude REAL,

                active INTEGER DEFAULT 1

            )
            """
        )


        # =================================================
        # CAMPUS BOUNDARY POINTS
        # =================================================
        #
        # Each campus can have its own service-area polygon.
        #
        # point_order controls the order in which the
        # coordinates are connected on the map.
        # =================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS campus_boundary_points (

                boundary_point_id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                campus_id INTEGER NOT NULL,

                point_order INTEGER NOT NULL,

                latitude REAL NOT NULL,

                longitude REAL NOT NULL,

                UNIQUE (
                    campus_id,
                    point_order
                )

            )
            """
        )


        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_campus_boundary_campus

            ON campus_boundary_points (
                campus_id,
                point_order
            )
            """
        )


        connection.commit()


        # =================================================
        # STUDENT COLUMNS
        # =================================================

        add_column_if_missing(
            cursor,
            "students",
            "email",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "students",
            "google_sub",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "students",
            "active",
            "INTEGER DEFAULT 1"
        )


        add_column_if_missing(
            cursor,
            "students",
            "created_at",
            "TEXT"
        )


        # =================================================
        # BIKE COLUMNS
        # =================================================

        add_column_if_missing(
            cursor,
            "bikes",
            "location",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "bikes",
            "last_updated",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "bikes",
            "station",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "bikes",
            "slot",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "bikes",
            "lock_status",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "bikes",
            "qr_secret",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "bikes",
            "active",
            "INTEGER DEFAULT 1"
        )


        # =================================================
        # RIDE COLUMNS
        # =================================================

        add_column_if_missing(
            cursor,
            "rides",
            "return_station",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "rides",
            "return_slot",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "rides",
            "start_station",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "rides",
            "start_slot",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "rides",
            "rent_method",
            "TEXT"
        )


        add_column_if_missing(
            cursor,
            "rides",
            "qr_verified",
            "INTEGER DEFAULT 0"
        )


        # =================================================
        # STATION COLUMNS
        # =================================================

        add_column_if_missing(
            cursor,
            "stations",
            "active",
            "INTEGER DEFAULT 1"
        )


        add_column_if_missing(
            cursor,
            "stations",
            "campus_id",
            "INTEGER"
        )


        add_column_if_missing(
            cursor,
            "stations",
            "latitude",
            "REAL"
        )


        add_column_if_missing(
            cursor,
            "stations",
            "longitude",
            "REAL"
        )


        # =================================================
        # PERMANENT STATION IDENTITY
        # =================================================
        #
        # station_code:
        #   STN001, STN002, ...
        #   Backend only. Never editable by Admin.
        #
        # display_name:
        #   Public location name such as Clubhouse.
        #
        # sponsor_name:
        #   Optional naming-rights brand such as Spotify.
        # =================================================

        add_column_if_missing(
            cursor,
            "stations",
            "station_code",
            "TEXT"
        )

        add_column_if_missing(
            cursor,
            "stations",
            "display_name",
            "TEXT"
        )

        add_column_if_missing(
            cursor,
            "stations",
            "sponsor_name",
            "TEXT"
        )


        # =================================================
        # STATION REFERENCES
        # =================================================

        add_column_if_missing(
            cursor,
            "bikes",
            "station_id",
            "INTEGER"
        )

        add_column_if_missing(
            cursor,
            "slots",
            "station_id",
            "INTEGER"
        )

        add_column_if_missing(
            cursor,
            "rides",
            "start_station_id",
            "INTEGER"
        )

        add_column_if_missing(
            cursor,
            "rides",
            "return_station_id",
            "INTEGER"
        )


        # =================================================
        # BACKFILL STATION CODES
        # =================================================

        cursor.execute(
            """
            UPDATE stations

            SET station_code =
                printf(
                    'STN%03d',
                    station_id
                )

            WHERE station_code IS NULL
               OR TRIM(station_code) = ''
            """
        )


        # Existing installations start with their current
        # name as the public display name.

        cursor.execute(
            """
            UPDATE stations

            SET display_name = station_name

            WHERE display_name IS NULL
               OR TRIM(display_name) = ''
            """
        )


        # =================================================
        # BACKFILL PERMANENT STATION REFERENCES
        # =================================================

        cursor.execute(
            """
            UPDATE bikes

            SET station_id = (
                SELECT s.station_id
                FROM stations s
                WHERE s.station_name = bikes.station
            )

            WHERE station IS NOT NULL
              AND station_id IS NULL
            """
        )


        cursor.execute(
            """
            UPDATE slots

            SET station_id = (
                SELECT s.station_id
                FROM stations s
                WHERE s.station_name = slots.station_name
            )

            WHERE station_name IS NOT NULL
              AND station_id IS NULL
            """
        )


        cursor.execute(
            """
            UPDATE rides

            SET start_station_id = (
                SELECT s.station_id
                FROM stations s
                WHERE s.station_name = rides.start_station
            )

            WHERE start_station IS NOT NULL
              AND start_station_id IS NULL
            """
        )


        cursor.execute(
            """
            UPDATE rides

            SET return_station_id = (
                SELECT s.station_id
                FROM stations s
                WHERE s.station_name = rides.return_station
            )

            WHERE return_station IS NOT NULL
              AND return_station_id IS NULL
            """
        )


        # station_code must always be unique.

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_stations_station_code

            ON stations(station_code)
            """
        )


        connection.commit()


        # =================================================
        # INDEXES
        # =================================================

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_students_email

            ON students(email)

            WHERE email IS NOT NULL
            """
        )


        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_students_google_sub

            ON students(google_sub)

            WHERE google_sub IS NOT NULL
            """
        )


        # =================================================
        # CLEAN DUPLICATE SLOT ROWS
        # =================================================

        cursor.execute(
            """
            DELETE FROM slots

            WHERE slot_id NOT IN (

                SELECT MIN(slot_id)

                FROM slots

                GROUP BY
                    station_name,
                    slot_number

            )
            """
        )


        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_station_slot

            ON slots(
                station_name,
                slot_number
            )
            """
        )


        connection.commit()


        # =================================================
        # DEFAULT CAMPUS
        # =================================================
        #
        # This stays in the database for multi-campus
        # capability. The mobile app does not need to show
        # "Campus 1" to students.
        # =================================================

        cursor.execute(
            """
            INSERT OR IGNORE INTO campuses (
                campus_name,
                active
            )
            VALUES (
                'Campus 1',
                1
            )
            """
        )


        default_campus = cursor.execute(
            """
            SELECT campus_id

            FROM campuses

            WHERE campus_name = 'Campus 1'

            LIMIT 1
            """
        ).fetchone()


        default_campus_id = (
            default_campus[0]
            if default_campus
            else None
        )


        # =================================================
        # ENSURE CURRENT STATIONS EXIST
        # =================================================
        #
        # IMPORTANT:
        # We no longer reset every station every time
        # Flask starts.
        # =================================================

        for station_name in ACTIVE_STATIONS:

            cursor.execute(
                """
                INSERT OR IGNORE INTO stations (
                    station_name,
                    total_slots,
                    active,
                    campus_id
                )
                VALUES (
                    ?,
                    4,
                    1,
                    ?
                )
                """,
                (
                    station_name,
                    default_campus_id,
                ),
            )


            # Assign a campus only if the station
            # currently has no campus.

            if default_campus_id is not None:

                cursor.execute(
                    """
                    UPDATE stations

                    SET campus_id = ?

                    WHERE station_name = ?
                      AND campus_id IS NULL
                    """,
                    (
                        default_campus_id,
                        station_name,
                    ),
                )


            station_row = cursor.execute(
                """
                SELECT total_slots

                FROM stations

                WHERE station_name = ?
                """,
                (
                    station_name,
                ),
            ).fetchone()


            total_slots = 4


            if (
                station_row
                and station_row[0]
                and station_row[0] > 0
            ):

                total_slots = station_row[0]


            # Make sure all station slots exist.

            for number in range(
                1,
                total_slots + 1
            ):

                slot_number = (
                    f"SLOT-{number:02d}"
                )


                cursor.execute(
                    """
                    INSERT OR IGNORE INTO slots (
                        station_name,
                        slot_number,
                        bike_id,
                        status
                    )

                    VALUES (
                        ?,
                        ?,
                        NULL,
                        'Available'
                    )
                    """,
                    (
                        station_name,
                        slot_number,
                    ),
                )


        connection.commit()


        # =================================================
        # DEVELOPMENT STUDENTS
        # =================================================

        for (
            student_id,
            student_name
        ) in DEFAULT_STUDENTS.items():

            cursor.execute(
                """
                INSERT OR IGNORE INTO students (
                    student_id,
                    name,
                    active
                )

                VALUES (
                    ?,
                    ?,
                    1
                )
                """,
                (
                    student_id,
                    student_name,
                ),
            )


        # =================================================
        # CREATE MISSING BIKES
        # =================================================
        #
        # A new bike is created without a slot first.
        # It will be parked below.
        # Existing bikes are NOT moved.
        # =================================================

        for (
            bike_id,
            preferred_station
        ) in DEFAULT_BIKES.items():

            cursor.execute(
                """
                SELECT bike_id

                FROM bikes

                WHERE bike_id = ?
                """,
                (
                    bike_id,
                ),
            )


            if cursor.fetchone() is None:

                cursor.execute(
                    """
                    INSERT INTO bikes (

                        bike_id,

                        status,

                        current_user,

                        total_rides,

                        location,

                        last_updated,

                        station,

                        slot,

                        lock_status,

                        qr_secret,

                        active

                    )

                    VALUES (

                        ?,

                        'Available',

                        NULL,

                        0,

                        NULL,

                        ?,

                        NULL,

                        NULL,

                        'Locked',

                        ?,

                        1

                    )
                    """,
                    (
                        bike_id,
                        india_time(),
                        secrets.token_urlsafe(24),
                    ),
                )


        # =================================================
        # MAKE SURE BIKES HAVE QR TOKENS
        # =================================================

        for bike_id in DEFAULT_BIKES:

            row = cursor.execute(
                """
                SELECT
                    qr_secret,
                    active

                FROM bikes

                WHERE bike_id = ?
                """,
                (
                    bike_id,
                ),
            ).fetchone()


            if not row:
                continue


            qr_secret = row[0]


            if not qr_secret:

                cursor.execute(
                    """
                    UPDATE bikes

                    SET qr_secret = ?

                    WHERE bike_id = ?
                    """,
                    (
                        secrets.token_urlsafe(24),
                        bike_id,
                    ),
                )


            # Only fix NULL.
            # Do NOT reactivate a bike deliberately disabled
            # by an administrator.

            cursor.execute(
                """
                UPDATE bikes

                SET active = 1

                WHERE bike_id = ?
                  AND active IS NULL
                """,
                (
                    bike_id,
                ),
            )


        connection.commit()


        # =================================================
        # REMOVE STALE / GHOST SLOT REFERENCES
        # =================================================
        #
        # Example:
        # Sports Ground previously claimed CB001 even though
        # CB001 was actually parked somewhere else.
        # =================================================

        cursor.execute(
            """
            UPDATE slots

            SET
                bike_id = NULL,
                status = 'Available'

            WHERE bike_id IS NOT NULL

              -- Reserved docks describe a pending return/movement, not
              -- the bike's current parking position. Never clear them
              -- merely because the bike is on a ride or in transit.
              AND status != 'Reserved'

              AND NOT EXISTS (

                  SELECT 1

                  FROM bikes b

                  WHERE b.bike_id = slots.bike_id

                    AND b.status IN ('Available', 'Maintenance')

                    AND b.station = slots.station_name

                    AND b.slot = slots.slot_number

              )
            """
        )


        connection.commit()


        # =================================================
        # PRESERVE REAL BIKE LOCATIONS
        # =================================================
        #
        # THIS IS THE IMPORTANT FIX.
        #
        # If:
        #
        # CB001 was returned to Library SLOT-02
        #
        # then after Flask restarts:
        #
        # CB001 stays at Library SLOT-02.
        #
        # DEFAULT_BIKES is only used when a bike has no valid
        # parking location.
        # =================================================

        for (
            bike_id,
            preferred_station
        ) in DEFAULT_BIKES.items():

            bike = cursor.execute(
                """
                SELECT

                    status,

                    current_user,

                    station,

                    slot

                FROM bikes

                WHERE bike_id = ?
                """,
                (
                    bike_id,
                ),
            ).fetchone()


            if not bike:
                continue


            status = bike[0]

            current_user = bike[1]

            current_station = bike[2]

            current_slot = bike[3]

            # Rebalancing is completed/cancelled explicitly by the admin.
            # Startup must never teleport an in-transit bike to a dock.
            if status == "Rebalancing":
                continue


            # =============================================
            # CHECK MAINTENANCE REPORTS
            # =============================================

            open_maintenance_report = cursor.execute(
                """
                SELECT report_id

                FROM maintenance_reports

                WHERE bike_id = ?
                  AND status != 'Resolved'
                  AND resolved_at IS NULL

                LIMIT 1
                """,
                (
                    bike_id,
                ),
            ).fetchone()


            parked_status = (
                "Maintenance"
                if open_maintenance_report
                else "Available"
            )


            # =============================================
            # BIKE IS CURRENTLY ON A RIDE
            # =============================================

            if status == "In use":

                # A bike being ridden may reserve, but not occupy, a slot.

                cursor.execute(
                    """
                    UPDATE slots

                    SET
                        bike_id = NULL,
                        status = 'Available'

                    WHERE bike_id = ?
                      AND status != 'Reserved'
                    """,
                    (
                        bike_id,
                    ),
                )


                cursor.execute(
                    """
                    UPDATE bikes

                    SET
                        location = 'On Ride',
                        station = NULL,
                        slot = NULL,
                        lock_status = 'Unlocked'

                    WHERE bike_id = ?
                    """,
                    (
                        bike_id,
                    ),
                )


                continue


            # =============================================
            # CHECK EXISTING PARKING LOCATION
            # =============================================

            parking_valid = False


            if (
                current_station
                and current_slot
            ):

                station_exists = cursor.execute(
                    """
                    SELECT
                        station_id,
                        active

                    FROM stations

                    WHERE station_name = ?
                    """,
                    (
                        current_station,
                    ),
                ).fetchone()


                slot_exists = cursor.execute(
                    """
                    SELECT
                        slot_id,
                        bike_id,
                        status

                    FROM slots

                    WHERE station_name = ?
                      AND slot_number = ?
                    """,
                    (
                        current_station,
                        current_slot,
                    ),
                ).fetchone()


                # Preserve the location when it belongs
                # to a valid active station.

                if (
                    station_exists
                    and station_exists[1] == 1
                    and slot_exists
                ):

                    parking_valid = True


            # =============================================
            # BIKE ALREADY HAS REAL PARKING
            # =============================================

            if parking_valid:

                # Clear duplicate references to this bike.

                cursor.execute(
                    """
                    UPDATE slots

                    SET
                        bike_id = NULL,
                        status = 'Available'

                    WHERE bike_id = ?

                      AND NOT (
                          station_name = ?
                          AND slot_number = ?
                      )
                    """,
                    (
                        bike_id,
                        current_station,
                        current_slot,
                    ),
                )


                current_slot_row = cursor.execute(
                    """
                    SELECT
                        slot_id,
                        bike_id

                    FROM slots

                    WHERE station_name = ?
                      AND slot_number = ?
                    """,
                    (
                        current_station,
                        current_slot,
                    ),
                ).fetchone()


                # Normally the correct slot is empty or
                # already contains this bike.

                if (
                    current_slot_row
                    and (
                        current_slot_row[1] is None
                        or
                        current_slot_row[1] == bike_id
                    )
                ):

                    cursor.execute(
                        """
                        UPDATE slots

                        SET
                            bike_id = ?,
                            status = 'Occupied'

                        WHERE slot_id = ?
                        """,
                        (
                            bike_id,
                            current_slot_row[0],
                        ),
                    )


                else:

                    # If another bike somehow occupies the
                    # same slot, find another free slot at
                    # the SAME station rather than resetting
                    # the bike to its original station.

                    free_slot = cursor.execute(
                        """
                        SELECT
                            slot_id,
                            slot_number

                        FROM slots

                        WHERE station_name = ?
                          AND status = 'Available'
                          AND bike_id IS NULL

                        ORDER BY slot_number

                        LIMIT 1
                        """,
                        (
                            current_station,
                        ),
                    ).fetchone()


                    if free_slot:

                        current_slot = (
                            free_slot[1]
                        )


                        cursor.execute(
                            """
                            UPDATE slots

                            SET
                                bike_id = ?,
                                status = 'Occupied'

                            WHERE slot_id = ?
                            """,
                            (
                                bike_id,
                                free_slot[0],
                            ),
                        )


                        cursor.execute(
                            """
                            UPDATE bikes

                            SET slot = ?

                            WHERE bike_id = ?
                            """,
                            (
                                current_slot,
                                bike_id,
                            ),
                        )


                cursor.execute(
                    """
                    UPDATE bikes

                    SET
                        status = ?,
                        current_user = NULL,
                        location = ?,
                        station = ?,
                        slot = ?,
                        lock_status = 'Locked'

                    WHERE bike_id = ?
                    """,
                    (
                        parked_status,
                        current_station,
                        current_station,
                        current_slot,
                        bike_id,
                    ),
                )


                continue


            # =============================================
            # BIKE HAS NO VALID PARKING LOCATION
            # =============================================
            #
            # ONLY here do we use its original/default
            # station.
            # =============================================

            free_slot = cursor.execute(
                """
                SELECT
                    slot_id,
                    slot_number

                FROM slots

                WHERE station_name = ?
                  AND status = 'Available'
                  AND bike_id IS NULL

                ORDER BY slot_number

                LIMIT 1
                """,
                (
                    preferred_station,
                ),
            ).fetchone()


            if not free_slot:

                # Do not overwrite another bike.
                # Leave this bike unplaced so the problem
                # can be fixed instead of corrupting data.

                cursor.execute(
                    """
                    UPDATE bikes

                    SET
                        status = ?,
                        current_user = NULL,
                        location = NULL,
                        station = NULL,
                        slot = NULL,
                        lock_status = 'Locked'

                    WHERE bike_id = ?
                    """,
                    (
                        parked_status,
                        bike_id,
                    ),
                )


                continue


            slot_id = free_slot[0]

            slot_number = free_slot[1]


            cursor.execute(
                """
                UPDATE slots

                SET
                    bike_id = ?,
                    status = 'Occupied'

                WHERE slot_id = ?
                """,
                (
                    bike_id,
                    slot_id,
                ),
            )


            cursor.execute(
                """
                UPDATE bikes

                SET
                    status = ?,
                    current_user = NULL,
                    location = ?,
                    station = ?,
                    slot = ?,
                    lock_status = 'Locked',
                    last_updated = ?

                WHERE bike_id = ?
                """,
                (
                    parked_status,
                    preferred_station,
                    preferred_station,
                    slot_number,
                    india_time(),
                    bike_id,
                ),
            )


        # =================================================
        # COMPLETE REFERENCES AFTER SEEDING/PARKING
        # =================================================
        # The earlier migration runs before new rows are created. Finish
        # these relationships here so a fresh database works on first boot.

        cursor.execute("""
            UPDATE stations SET station_code = printf('STN%03d', station_id)
            WHERE station_code IS NULL OR TRIM(station_code) = ''
        """)
        cursor.execute("""
            UPDATE stations SET display_name = station_name
            WHERE display_name IS NULL OR TRIM(display_name) = ''
        """)
        cursor.execute("""
            UPDATE slots SET station_id = (
                SELECT station_id FROM stations
                WHERE stations.station_name = slots.station_name
            ) WHERE station_id IS NULL
        """)
        cursor.execute("""
            UPDATE bikes SET station_id = (
                SELECT station_id FROM stations
                WHERE stations.station_name = bikes.station
            )
        """)

        # =================================================
        # KEEP TOTAL RIDES CORRECT
        # =================================================

        cursor.execute(
            """
            UPDATE bikes

            SET total_rides = (

                SELECT COUNT(*)

                FROM rides

                WHERE rides.bike_id =
                      bikes.bike_id

                  AND rides.returned_at
                      IS NOT NULL

            )
            """
        )


        connection.commit()


    finally:

        connection.close()


# =========================================================
# DIRECT RUN
# =========================================================

if __name__ == "__main__":

    initialize_database()

    print(
        "CampusBike database ready."
    )
