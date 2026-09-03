from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo

import hmac
import io
import json
import os
import re
import sqlite3

import qrcode

from database import (
    ACTIVE_STATIONS,
    DB_NAME,
    initialize_database,
)

from mobile_api import mobile_api


# =========================================================
# INITIAL SETUP
# =========================================================

load_dotenv()

initialize_database()


app = Flask(__name__)


app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-before-deployment",
)


app.config.update(

    SESSION_COOKIE_HTTPONLY=True,

    SESSION_COOKIE_SAMESITE="Lax",

    SESSION_COOKIE_SECURE=
        os.environ.get(
            "SESSION_COOKIE_SECURE",
            "0",
        ) == "1",

)


# =========================================================
# CSRF
# =========================================================

csrf = CSRFProtect(app)


# =========================================================
# MOBILE API
# =========================================================

app.register_blueprint(
    mobile_api
)

csrf.exempt(
    mobile_api
)


# =========================================================
# GOOGLE LOGIN
# =========================================================

oauth = OAuth(app)


GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "",
).strip()


GOOGLE_CLIENT_SECRET = os.environ.get(
    "GOOGLE_CLIENT_SECRET",
    "",
).strip()


GOOGLE_READY = bool(
    GOOGLE_CLIENT_ID
    and GOOGLE_CLIENT_SECRET
)


if GOOGLE_READY:

    oauth.register(

        name="google",

        client_id=
            GOOGLE_CLIENT_ID,

        client_secret=
            GOOGLE_CLIENT_SECRET,

        server_metadata_url=
            "https://accounts.google.com/.well-known/openid-configuration",

        client_kwargs={
            "scope":
                "openid profile email"
        },

    )


ALLOWED_EMAIL_DOMAINS = {

    item.strip()
    .lower()
    .lstrip("@")

    for item in os.environ.get(
        "ALLOWED_EMAIL_DOMAINS",
        "",
    ).split(",")

    if item.strip()

}


# =========================================================
# ADMIN LOGIN
# =========================================================

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "admin",
)


ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "campusbike123",
)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    connection = sqlite3.connect(
        DB_NAME
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


# =========================================================
# TIME
# =========================================================

def now_ist():

    return datetime.now(
        ZoneInfo(
            "Asia/Kolkata"
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =========================================================
# SAFE REDIRECT
# =========================================================

def is_safe_next(value):

    return bool(
        value
        and value.startswith("/")
        and not value.startswith("//")
    )


# =========================================================
# STUDENT LOGIN PROTECTION
# =========================================================

def student_required(view):

    @wraps(view)

    def wrapped(
        *args,
        **kwargs,
    ):

        if not session.get(
            "student_id"
        ):

            next_url = (

                request.full_path

                if request.query_string

                else request.path

            )

            return redirect(

                url_for(
                    "student_login",
                    next=next_url,
                )

            )

        return view(
            *args,
            **kwargs,
        )

    return wrapped


# =========================================================
# ADMIN LOGIN PROTECTION
# =========================================================

def admin_required(view):

    @wraps(view)

    def wrapped(
        *args,
        **kwargs,
    ):

        if not session.get(
            "admin_logged_in"
        ):

            return redirect(
                url_for(
                    "admin_login"
                )
            )

        return view(
            *args,
            **kwargs,
        )

    return wrapped


# =========================================================
# CURRENT STUDENT
# =========================================================

def current_student(
    connection=None
):

    student_id = session.get(
        "student_id"
    )


    if not student_id:

        return None


    owns_connection = (
        connection is None
    )


    if owns_connection:

        connection = get_db()


    row = connection.execute(

        """
        SELECT
            student_id,
            name,
            email,
            active

        FROM students

        WHERE student_id = ?
        """,

        (
            student_id,
        ),

    ).fetchone()


    if owns_connection:

        connection.close()


    return row


# =========================================================
# STATION SUMMARY
# =========================================================

def get_station_summary(
    connection
):

    return connection.execute(

        """
        SELECT

            s.station_id,

            s.station_name,

            COALESCE(
                NULLIF(
                    TRIM(s.display_name),
                    ''
                ),
                s.station_name
            ) AS display_name,

            s.sponsor_name,

            s.latitude,

            s.longitude,

            s.total_slots,


            (
                SELECT COUNT(*)

                FROM slots sl

                WHERE
                    sl.station_name =
                        s.station_name

                    AND
                    sl.status =
                        'Available'

            ) AS available_slots,


            (
                SELECT COUNT(*)

                FROM slots sl

                WHERE
                    sl.station_name =
                        s.station_name

                    AND
                    sl.status =
                        'Occupied'

            ) AS occupied_slots,


            (
                SELECT COUNT(*)

                FROM bikes b

                WHERE
                    b.station =
                        s.station_name

                    AND
                    b.status =
                        'Available'

                    AND
                    COALESCE(
                        b.active,
                        1
                    ) = 1

            ) AS available_bikes


        FROM stations s


        WHERE
            COALESCE(
                s.active,
                1
            ) = 1


        ORDER BY
            s.station_id
        """

    ).fetchall()


# =========================================================
# CREATE STUDENT ID
# =========================================================

def make_student_id(
    connection,
    email,
):

    prefix = email.split(
        "@",
        1,
    )[0]


    base = re.sub(
        r"[^A-Za-z0-9]",
        "",
        prefix,
    ).upper()[:18] or "STUDENT"


    candidate = base

    counter = 2


    while connection.execute(

        """
        SELECT 1

        FROM students

        WHERE student_id = ?
        """,

        (
            candidate,
        ),

    ).fetchone():

        candidate = (
            f"{base[:15]}{counter}"
        )

        counter += 1


    return candidate


# =========================================================
# QR
# =========================================================

def qr_payload(
    bike
):

    return (
        f"CAMPUSBIKE|"
        f"{bike['bike_id']}|"
        f"{bike['qr_secret']}"
    )


def parse_qr_payload(
    text
):

    parts = (
        text
        or ""
    ).strip().split("|")


    if (
        len(parts) != 3

        or

        parts[0] != "CAMPUSBIKE"
    ):

        return None, None


    return (
        parts[1].upper(),
        parts[2],
    )


# =========================================================
# STUDENT LOGIN PAGE
# =========================================================

@app.route(
    "/login"
)

def student_login():

    if session.get(
        "student_id"
    ):

        return redirect(
            url_for(
                "dashboard"
            )
        )


    next_url = request.args.get(
        "next",
        "",
    )


    if is_safe_next(
        next_url
    ):

        session[
            "student_next"
        ] = next_url


    return render_template(

        "login.html",

        google_ready=
            GOOGLE_READY,

        allowed_domains=
            sorted(
                ALLOWED_EMAIL_DOMAINS
            ),

    )


# =========================================================
# GOOGLE LOGIN
# =========================================================

@app.route(
    "/auth/google"
)

def google_login():

    if not GOOGLE_READY:

        flash(

            "Google login is not configured yet. "
            "Add the OAuth credentials in .env.",

            "error",

        )

        return redirect(
            url_for(
                "student_login"
            )
        )


    redirect_uri = url_for(
        "google_callback",
        _external=True,
    )


    return (
        oauth.google
        .authorize_redirect(

            redirect_uri,

            prompt=
                "select_account",

        )
    )


# =========================================================
# GOOGLE CALLBACK
# =========================================================

@app.route(
    "/auth/google/callback"
)

def google_callback():

    if not GOOGLE_READY:

        return redirect(
            url_for(
                "student_login"
            )
        )


    try:

        token = (
            oauth.google
            .authorize_access_token()
        )

        userinfo = (
            token.get(
                "userinfo"
            )
            or {}
        )


    except Exception:

        flash(
            "Google sign-in failed. Please try again.",
            "error",
        )

        return redirect(
            url_for(
                "student_login"
            )
        )


    email = str(
        userinfo.get(
            "email",
            "",
        )
    ).strip().lower()


    name = str(
        userinfo.get(
            "name",
            "Student",
        )
    ).strip() or "Student"


    google_sub = str(
        userinfo.get(
            "sub",
            "",
        )
    ).strip()


    email_verified = (
        userinfo.get(
            "email_verified",
            False,
        )
    )


    if (
        not email

        or
        not google_sub

        or
        not email_verified
    ):

        flash(
            "Google did not return a verified email address.",
            "error",
        )

        return redirect(
            url_for(
                "student_login"
            )
        )


    domain = email.rsplit(
        "@",
        1,
    )[-1]


    if (
        ALLOWED_EMAIL_DOMAINS

        and

        domain
        not in
        ALLOWED_EMAIL_DOMAINS
    ):

        flash(
            "This Google account is not from an approved college email domain.",
            "error",
        )

        return redirect(
            url_for(
                "student_login"
            )
        )


    connection = get_db()


    student = connection.execute(

        """
        SELECT student_id

        FROM students

        WHERE
            google_sub = ?

            OR

            email = ?

        LIMIT 1
        """,

        (
            google_sub,
            email,
        ),

    ).fetchone()


    if student:

        student_id = (
            student[
                "student_id"
            ]
        )


        connection.execute(

            """
            UPDATE students

            SET
                name = ?,
                email = ?,
                google_sub = ?,
                active = 1

            WHERE
                student_id = ?
            """,

            (
                name,
                email,
                google_sub,
                student_id,
            ),

        )


    else:

        student_id = (
            make_student_id(
                connection,
                email,
            )
        )


        connection.execute(

            """
            INSERT INTO students (

                student_id,
                name,
                email,
                google_sub,
                active,
                created_at

            )

            VALUES (
                ?,
                ?,
                ?,
                ?,
                1,
                ?
            )
            """,

            (
                student_id,
                name,
                email,
                google_sub,
                now_ist(),
            ),

        )


    connection.commit()

    connection.close()


    next_url = session.get(
        "student_next"
    )


    session.clear()


    session[
        "student_id"
    ] = student_id


    session[
        "student_email"
    ] = email


    session[
        "student_name"
    ] = name


    return redirect(

        next_url

        if is_safe_next(
            next_url
        )

        else

        url_for(
            "dashboard"
        )

    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@app.route(
    "/logout"
)

def student_logout():

    session.clear()

    return redirect(
        url_for(
            "student_login"
        )
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route(
    "/"
)

@student_required

def dashboard():

    connection = get_db()


    student = current_student(
        connection
    )


    if (
        not student

        or

        not student[
            "active"
        ]
    ):

        connection.close()

        session.clear()

        return redirect(
            url_for(
                "student_login"
            )
        )


    active_ride = connection.execute(

        """
        SELECT *

        FROM rides

        WHERE
            student_id = ?

            AND

            returned_at IS NULL

        ORDER BY
            ride_id DESC

        LIMIT 1
        """,

        (
            student[
                "student_id"
            ],
        ),

    ).fetchone()


    completed_count = (
        connection.execute(

            """
            SELECT COUNT(*)

            FROM rides

            WHERE
                student_id = ?

                AND

                returned_at
                    IS NOT NULL
            """,

            (
                student[
                    "student_id"
                ],
            ),

        ).fetchone()[0]
    )


    recent_rides = (
        connection.execute(

            """
            SELECT *

            FROM rides

            WHERE student_id = ?

            ORDER BY
                ride_id DESC

            LIMIT 10
            """,

            (
                student[
                    "student_id"
                ],
            ),

        ).fetchall()
    )


    stations = (
        get_station_summary(
            connection
        )
    )


    connection.close()


    return render_template(

        "dashboard.html",

        student=
            student,

        active_ride=
            active_ride,

        completed_count=
            completed_count,

        recent_rides=
            recent_rides,

        stations=
            stations,

    )


# =========================================================
# STATION
# =========================================================

@app.route(
    "/station/<path:station_name>"
)

@student_required

def station_view(
    station_name
):

    connection = get_db()


    student = current_student(
        connection
    )


    station = connection.execute(

        """
        SELECT
            station_name,
            total_slots

        FROM stations

        WHERE
            station_name = ?

            AND

            COALESCE(
                active,
                1
            ) = 1
        """,

        (
            station_name,
        ),

    ).fetchone()


    if not station:

        connection.close()

        abort(404)


    bikes = connection.execute(

        """
        SELECT

            bike_id,
            status,
            station,
            slot,
            lock_status,
            total_rides

        FROM bikes

        WHERE
            station = ?

            AND
            status =
                'Available'

            AND
            COALESCE(
                active,
                1
            ) = 1

        ORDER BY
            bike_id
        """,

        (
            station_name,
        ),

    ).fetchall()


    active_ride = connection.execute(

        """
        SELECT
            ride_id,
            bike_id

        FROM rides

        WHERE
            student_id = ?

            AND

            returned_at
                IS NULL

        LIMIT 1
        """,

        (
            student[
                "student_id"
            ],
        ),

    ).fetchone()


    connection.close()


    return render_template(

        "station.html",

        student=
            student,

        station=
            station,

        bikes=
            bikes,

        active_ride=
            active_ride,

    )


# =========================================================
# BIKE
# =========================================================

@app.route(
    "/bike/<bike_id>"
)

@student_required

def bike_view(
    bike_id
):

    bike_id = (
        bike_id.upper()
    )


    connection = get_db()


    student = current_student(
        connection
    )


    bike = connection.execute(

        """
        SELECT

            bike_id,
            status,
            station,
            slot,
            lock_status,
            total_rides

        FROM bikes

        WHERE
            bike_id = ?

            AND

            COALESCE(
                active,
                1
            ) = 1
        """,

        (
            bike_id,
        ),

    ).fetchone()


    if not bike:

        connection.close()

        abort(404)


    active_ride = connection.execute(

        """
        SELECT
            ride_id,
            bike_id

        FROM rides

        WHERE
            student_id = ?

            AND

            returned_at
                IS NULL

        LIMIT 1
        """,

        (
            student[
                "student_id"
            ],
        ),

    ).fetchone()


    connection.close()


    return render_template(

        "bike.html",

        student=
            student,

        bike=
            bike,

        active_ride=
            active_ride,

    )


# =========================================================
# SCAN BIKE WEB
# =========================================================

@app.route(
    "/scan/<bike_id>"
)

@student_required

def scan_bike(
    bike_id
):

    bike_id = (
        bike_id.upper()
    )


    connection = get_db()


    student = current_student(
        connection
    )


    active_ride = connection.execute(

        """
        SELECT
            ride_id,
            bike_id

        FROM rides

        WHERE
            student_id = ?

            AND

            returned_at
                IS NULL

        LIMIT 1
        """,

        (
            student[
                "student_id"
            ],
        ),

    ).fetchone()


    if active_ride:

        connection.close()

        flash(
            "Finish your current ride before renting another bike.",
            "error",
        )

        return redirect(
            url_for(
                "dashboard"
            )
        )


    bike = connection.execute(

        """
        SELECT

            bike_id,
            status,
            station,
            slot,
            lock_status

        FROM bikes

        WHERE
            bike_id = ?

            AND

            COALESCE(
                active,
                1
            ) = 1
        """,

        (
            bike_id,
        ),

    ).fetchone()


    connection.close()


    if not bike:

        abort(404)


    if (
        bike[
            "status"
        ]
        !=
        "Available"
    ):

        flash(
            "That bike is no longer available.",
            "error",
        )

        return redirect(
            url_for(
                "dashboard"
            )
        )


    return render_template(

        "scan.html",

        student=
            student,

        bike=
            bike,

    )


# =========================================================
# WEB QR VERIFY AND RENT
# =========================================================

@app.route(
    "/api/verify-and-rent",
    methods=["POST"],
)

def verify_and_rent():

    student_id = session.get(
        "student_id"
    )


    if not student_id:

        return jsonify({

            "ok":
                False,

            "message":
                "Please sign in again.",

        }), 401


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    selected_bike_id = str(
        data.get(
            "bike_id",
            "",
        )
    ).strip().upper()


    scanned_text = str(
        data.get(
            "qr_text",
            "",
        )
    ).strip()


    (
        scanned_bike_id,
        scanned_secret,

    ) = parse_qr_payload(
        scanned_text
    )


    if not scanned_bike_id:

        return jsonify({

            "ok":
                False,

            "message":
                "This is not a CampusBike QR code.",

        }), 400


    if (
        scanned_bike_id
        !=
        selected_bike_id
    ):

        return jsonify({

            "ok":
                False,

            "message":
                (
                    f"Wrong bike scanned. "
                    f"You selected "
                    f"{selected_bike_id}, "
                    f"but scanned "
                    f"{scanned_bike_id}."
                ),

        }), 400


    connection = get_db()


    try:

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        active = connection.execute(

            """
            SELECT ride_id

            FROM rides

            WHERE
                student_id = ?

                AND

                returned_at
                    IS NULL

            LIMIT 1
            """,

            (
                student_id,
            ),

        ).fetchone()


        if active:

            connection.rollback()

            return jsonify({

                "ok":
                    False,

                "message":
                    "You already have an active ride.",

            }), 409


        bike = connection.execute(

            """
            SELECT

                bike_id,
                status,
                current_user,
                station,
                slot,
                qr_secret

            FROM bikes

            WHERE
                bike_id = ?

                AND

                COALESCE(
                    active,
                    1
                ) = 1
            """,

            (
                selected_bike_id,
            ),

        ).fetchone()


        if not bike:

            connection.rollback()

            return jsonify({

                "ok":
                    False,

                "message":
                    "Bike not found.",

            }), 404


        if (
            bike[
                "status"
            ]
            !=
            "Available"
        ):

            connection.rollback()

            return jsonify({

                "ok":
                    False,

                "message":
                    "This bike is no longer available.",

            }), 409


        if (

            not scanned_secret

            or

            not hmac.compare_digest(

                scanned_secret,

                bike[
                    "qr_secret"
                ]
                or "",

            )

        ):

            connection.rollback()

            return jsonify({

                "ok":
                    False,

                "message":
                    "QR verification failed.",

            }), 400


        start_station = (
            bike[
                "station"
            ]
        )


        start_slot = (
            bike[
                "slot"
            ]
        )


        if (
            start_station
            and start_slot
        ):

            connection.execute(

                """
                UPDATE slots

                SET
                    status =
                        'Available',

                    bike_id =
                        NULL

                WHERE
                    station_name = ?

                    AND
                    slot_number = ?

                    AND
                    bike_id = ?
                """,

                (
                    start_station,
                    start_slot,
                    selected_bike_id,
                ),

            )


        timestamp = now_ist()


        updated = (
            connection.execute(

                """
                UPDATE bikes

                SET
                    status =
                        'In use',

                    current_user =
                        ?,

                    location =
                        'On Ride',

                    station =
                        NULL,

                    slot =
                        NULL,

                    lock_status =
                        'Unlocked',

                    last_updated =
                        ?

                WHERE
                    bike_id = ?

                    AND

                    status =
                        'Available'
                """,

                (
                    student_id,
                    timestamp,
                    selected_bike_id,
                ),

            )
        )


        if updated.rowcount != 1:

            connection.rollback()

            return jsonify({

                "ok":
                    False,

                "message":
                    "The bike was just taken by someone else.",

            }), 409


        connection.execute(

            """
            INSERT INTO rides (

                bike_id,
                student_id,
                rented_at,
                returned_at,
                return_station,
                return_slot,
                start_station,
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
                'qr-camera',
                1
            )
            """,

            (
                selected_bike_id,
                student_id,
                timestamp,
                start_station,
                start_slot,
            ),

        )


        connection.commit()


    except sqlite3.Error:

        connection.rollback()

        return jsonify({

            "ok":
                False,

            "message":
                "Database error. Please try again.",

        }), 500


    finally:

        connection.close()


    return jsonify({

        "ok":
            True,

        "redirect":
            url_for(
                "dashboard"
            ),

    })


# =========================================================
# WEB RETURN RIDE
# =========================================================

@app.route(
    "/return/<int:ride_id>",
    methods=[
        "GET",
        "POST",
    ],
)

@student_required

def return_ride(
    ride_id
):

    student_id = (
        session[
            "student_id"
        ]
    )


    connection = get_db()


    ride = connection.execute(

        """
        SELECT *

        FROM rides

        WHERE
            ride_id = ?

            AND

            student_id = ?

            AND

            returned_at
                IS NULL
        """,

        (
            ride_id,
            student_id,
        ),

    ).fetchone()


    if not ride:

        connection.close()

        abort(404)


    if (
        request.method
        ==
        "POST"
    ):

        station_name = (
            request.form.get(
                "station_name",
                "",
            ).strip()
        )


        try:

            connection.execute(
                "BEGIN IMMEDIATE"
            )


            station = (
                connection.execute(

                    """
                    SELECT
                        station_name

                    FROM stations

                    WHERE
                        station_name = ?

                        AND

                        COALESCE(
                            active,
                            1
                        ) = 1
                    """,

                    (
                        station_name,
                    ),

                ).fetchone()
            )


            if not station:

                connection.rollback()

                flash(
                    "Choose a valid CampusBike station.",
                    "error",
                )

                return redirect(

                    url_for(
                        "return_ride",
                        ride_id=ride_id,
                    )

                )


            slot = connection.execute(

                """
                SELECT
                    slot_id,
                    slot_number

                FROM slots

                WHERE
                    station_name = ?

                    AND

                    status =
                        'Available'

                ORDER BY
                    slot_number

                LIMIT 1
                """,

                (
                    station_name,
                ),

            ).fetchone()


            if not slot:

                connection.rollback()

                flash(
                    "That station is full. Choose another station.",
                    "error",
                )

                return redirect(

                    url_for(
                        "return_ride",
                        ride_id=ride_id,
                    )

                )


            bike = connection.execute(

                """
                SELECT

                    bike_id,
                    current_user,
                    status

                FROM bikes

                WHERE
                    bike_id = ?
                """,

                (
                    ride[
                        "bike_id"
                    ],
                ),

            ).fetchone()


            if (

                not bike

                or

                bike[
                    "current_user"
                ]
                !=
                student_id

                or

                bike[
                    "status"
                ]
                !=
                "In use"

            ):

                connection.rollback()

                flash(
                    "This active ride could not be verified.",
                    "error",
                )

                return redirect(
                    url_for(
                        "dashboard"
                    )
                )


            occupied = (
                connection.execute(

                    """
                    UPDATE slots

                    SET
                        status =
                            'Occupied',

                        bike_id =
                            ?

                    WHERE
                        slot_id = ?

                        AND

                        status =
                            'Available'
                    """,

                    (
                        bike[
                            "bike_id"
                        ],

                        slot[
                            "slot_id"
                        ],
                    ),

                )
            )


            if (
                occupied.rowcount
                != 1
            ):

                connection.rollback()

                flash(
                    "That slot was just taken. Choose the station again.",
                    "error",
                )

                return redirect(

                    url_for(
                        "return_ride",
                        ride_id=ride_id,
                    )

                )


            timestamp = now_ist()


            connection.execute(

                """
                UPDATE bikes

                SET
                    status =
                        'Available',

                    current_user =
                        NULL,

                    location =
                        ?,

                    station =
                        ?,

                    slot =
                        ?,

                    lock_status =
                        'Locked',

                    total_rides =
                        total_rides + 1,

                    last_updated =
                        ?

                WHERE
                    bike_id = ?
                """,

                (
                    station_name,
                    station_name,

                    slot[
                        "slot_number"
                    ],

                    timestamp,

                    bike[
                        "bike_id"
                    ],
                ),

            )


            connection.execute(

                """
                UPDATE rides

                SET
                    returned_at =
                        ?,

                    return_station =
                        ?,

                    return_slot =
                        ?

                WHERE
                    ride_id = ?

                    AND

                    returned_at
                        IS NULL
                """,

                (
                    timestamp,
                    station_name,

                    slot[
                        "slot_number"
                    ],

                    ride_id,
                ),

            )


            connection.commit()


            flash(

                (
                    f"Ride completed. "
                    f"Park "
                    f"{bike['bike_id']} "
                    f"at "
                    f"{station_name}, "
                    f"{slot['slot_number']}."
                ),

                "success",

            )


            return redirect(
                url_for(
                    "dashboard"
                )
            )


        except sqlite3.Error:

            connection.rollback()

            flash(
                "Database error. Please try again.",
                "error",
            )

            return redirect(

                url_for(
                    "return_ride",
                    ride_id=ride_id,
                )

            )


        finally:

            connection.close()


    stations = get_station_summary(
        connection
    )


    student = current_student(
        connection
    )


    connection.close()


    return render_template(

        "return.html",

        student=
            student,

        ride=
            ride,

        stations=
            stations,

    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=[
        "GET",
        "POST",
    ],
)

def admin_login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for(
                "admin_dashboard"
            )
        )


    error = None


    if (
        request.method
        ==
        "POST"
    ):

        username = (
            request.form.get(
                "username",
                "",
            ).strip()
        )


        password = (
            request.form.get(
                "password",
                "",
            )
        )


        if (

            hmac.compare_digest(
                username,
                ADMIN_USERNAME,
            )

            and

            hmac.compare_digest(
                password,
                ADMIN_PASSWORD,
            )

        ):

            session.clear()


            session[
                "admin_logged_in"
            ] = True


            session[
                "admin_username"
            ] = username


            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )


        error = (
            "Incorrect username or password."
        )


    return render_template(

        "admin_login.html",

        error=
            error,

    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route(
    "/admin/logout"
)

def admin_logout():

    session.clear()

    return redirect(
        url_for(
            "admin_login"
        )
    )


# =========================================================
# BIKE MOVEMENT SCHEMA
# =========================================================

def ensure_bike_movements_schema(
    connection
):

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            bike_movements (

                movement_id
                    INTEGER PRIMARY KEY AUTOINCREMENT,

                bike_id
                    TEXT NOT NULL,

                movement_type
                    TEXT NOT NULL,

                from_station_id
                    INTEGER,

                from_station_name
                    TEXT,

                from_slot
                    TEXT,

                to_station_id
                    INTEGER NOT NULL,

                to_station_name
                    TEXT NOT NULL,

                to_slot
                    TEXT NOT NULL,

                admin_username
                    TEXT,

                moved_at
                    TEXT NOT NULL,

                movement_status
                    TEXT DEFAULT 'Completed',

                started_at
                    TEXT,

                completed_at
                    TEXT
            )
        """
    )


    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(bike_movements)"
        ).fetchall()
    }


    if "movement_status" not in columns:

        connection.execute(
            """
            ALTER TABLE bike_movements
            ADD COLUMN movement_status
                TEXT DEFAULT 'Completed'
            """
        )


    if "started_at" not in columns:

        connection.execute(
            """
            ALTER TABLE bike_movements
            ADD COLUMN started_at TEXT
            """
        )


    if "completed_at" not in columns:

        connection.execute(
            """
            ALTER TABLE bike_movements
            ADD COLUMN completed_at TEXT
            """
        )


    # Old movements were already completed.
    connection.execute(
        """
        UPDATE bike_movements

        SET movement_status =
            COALESCE(
                movement_status,
                'Completed'
            )
        """
    )


    connection.execute(
        """
        UPDATE bike_movements

        SET started_at =
            COALESCE(
                started_at,
                moved_at
            )
        """
    )


    connection.execute(
        """
        UPDATE bike_movements

        SET completed_at =
            COALESCE(
                completed_at,
                moved_at
            )

        WHERE
            movement_status = 'Completed'
        """
    )


    connection.commit()


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    "/admin"
)

@admin_required

def admin_dashboard():

    connection = get_db()


    # -----------------------------------------------------
    # DASHBOARD STATS
    # -----------------------------------------------------

    stats = {

        "total_bikes":

            connection.execute(

                """
                SELECT COUNT(*)

                FROM bikes

                WHERE
                    COALESCE(
                        active,
                        1
                    ) = 1
                """

            ).fetchone()[0],


        "available_bikes":

            connection.execute(

                """
                SELECT COUNT(*)

                FROM bikes

                WHERE
                    status =
                        'Available'

                    AND

                    COALESCE(
                        active,
                        1
                    ) = 1
                """

            ).fetchone()[0],


        "in_use":

            connection.execute(

                """
                SELECT COUNT(*)

                FROM bikes

                WHERE
                    status =
                        'In use'

                    AND

                    COALESCE(
                        active,
                        1
                    ) = 1
                """

            ).fetchone()[0],


        "active_rides":

            connection.execute(

                """
                SELECT COUNT(*)

                FROM rides

                WHERE
                    returned_at
                        IS NULL
                """

            ).fetchone()[0],


        "completed_rides":

            connection.execute(

                """
                SELECT COUNT(*)

                FROM rides

                WHERE
                    returned_at
                        IS NOT NULL
                """

            ).fetchone()[0],


        "students":

            connection.execute(

                """
                SELECT COUNT(*)

                FROM students

                WHERE
                    email IS NOT NULL

                    AND

                    COALESCE(
                        active,
                        1
                    ) = 1
                """

            ).fetchone()[0],

    }


    # -----------------------------------------------------
    # STATIONS
    # -----------------------------------------------------

    stations = (
        get_station_summary(
            connection
        )
    )


    # -----------------------------------------------------
    # BIKES
    # -----------------------------------------------------

    ensure_bike_movements_schema(
        connection
    )


    bikes = connection.execute(
        """
        SELECT

            b.bike_id,
            b.status,
            b.current_user,
            b.total_rides,
            b.station,
            b.station_id,
            b.slot,
            b.lock_status,

            COALESCE(
                s.campus_id,
                source_station.campus_id
            ) AS campus_id,

            TRIM(
                COALESCE(
                    s.sponsor_name || ' ',
                    ''
                )
                ||
                COALESCE(
                    s.display_name,
                    s.station_name,
                    b.station
                )
            ) AS station_public_name,

            movement.movement_id
                AS pending_movement_id,

            movement.to_station_id
                AS planned_station_id,

            movement.to_station_name
                AS planned_station_name,

            movement.to_slot
                AS planned_slot,

            movement.started_at
                AS movement_started_at


        FROM bikes b


        LEFT JOIN stations s

            ON
                s.station_id =
                    b.station_id


        LEFT JOIN bike_movements movement

            ON
                movement.movement_id = (

                    SELECT
                        MAX(m2.movement_id)

                    FROM bike_movements m2

                    WHERE
                        m2.bike_id =
                            b.bike_id

                        AND

                        m2.movement_status =
                            'In Transit'
                )


        LEFT JOIN stations source_station

            ON
                source_station.station_id =
                    movement.from_station_id


        WHERE
            COALESCE(
                b.active,
                1
            ) = 1


        ORDER BY
            b.bike_id
        """
    ).fetchall()


    # -----------------------------------------------------
    # REBALANCING DESTINATIONS
    # -----------------------------------------------------

    rebalance_stations = connection.execute(
        """
        SELECT

            station_id,
            campus_id,

            TRIM(
                COALESCE(
                    sponsor_name || ' ',
                    ''
                )
                ||
                COALESCE(
                    display_name,
                    station_name
                )
            ) AS public_name

        FROM stations

        WHERE
            COALESCE(
                active,
                1
            ) = 1

        ORDER BY
            campus_id,
            station_id
        """
    ).fetchall()


    # -----------------------------------------------------
    # MOVEMENT HISTORY
    # -----------------------------------------------------

    bike_movements = connection.execute(
        """
        SELECT

            movement_id,
            bike_id,
            movement_type,

            from_station_id,
            from_station_name,
            from_slot,

            to_station_id,
            to_station_name,
            to_slot,

            admin_username,

            movement_status,
            started_at,
            completed_at,
            moved_at

        FROM bike_movements

        ORDER BY
            movement_id DESC

        LIMIT 30
        """
    ).fetchall()


    # -----------------------------------------------------
    # RIDES
    # -----------------------------------------------------

    rides = connection.execute(

        """
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

        ORDER BY
            ride_id DESC

        LIMIT 100
        """

    ).fetchall()


    # -----------------------------------------------------
    # STUDENTS
    # -----------------------------------------------------

    students = connection.execute(

        """
        SELECT

            student_id,
            name,
            email,
            active,
            created_at

        FROM students

        WHERE
            email IS NOT NULL

        ORDER BY

            created_at DESC,

            student_id
        """

    ).fetchall()


    # -----------------------------------------------------
    # SLOTS
    # -----------------------------------------------------

    slots = connection.execute(

        """
        SELECT

            sl.station_name,
            sl.slot_number,
            sl.bike_id,
            sl.status

        FROM slots sl

        JOIN stations s

            ON
            s.station_name =
                sl.station_name

        WHERE
            COALESCE(
                s.active,
                1
            ) = 1

        ORDER BY

            s.station_id,

            sl.slot_number
        """

    ).fetchall()


    # =====================================================
    # MAINTENANCE REPORTS
    # =====================================================

    maintenance_reports = (
        connection.execute(

            """
            SELECT

                report_id,
                bike_id,
                student_id,
                issue_type,
                description,
                status,
                severity,
                reported_at,
                resolved_at

            FROM maintenance_reports

            ORDER BY

                CASE status

                    WHEN 'Reported'
                        THEN 1

                    WHEN 'Under Inspection'
                        THEN 2

                    WHEN 'Maintenance'
                        THEN 3

                    WHEN 'Ready'
                        THEN 4

                    WHEN 'Resolved'
                        THEN 5

                    ELSE 6

                END,

                report_id DESC
            """

        ).fetchall()
    )


    connection.close()


    # -----------------------------------------------------
    # SEND EVERYTHING TO ADMIN.HTML
    # -----------------------------------------------------

    return render_template(

        "admin.html",

        stats=
            stats,

        stations=
            stations,

        bikes=
            bikes,

        rebalance_stations=
            rebalance_stations,

        bike_movements=
            bike_movements,

        rides=
            rides,

        students=
            students,

        slots=
            slots,

        maintenance_reports=
            maintenance_reports,

    )



# =========================================================
# ADMIN MAINTENANCE UPDATE
# =========================================================

@app.route(
    "/admin/maintenance/<int:report_id>",
    methods=["POST"],
)
@admin_required
def admin_maintenance_update(report_id):

    new_status = request.form.get(
        "status",
        "",
    ).strip()

    allowed_statuses = {
        "Reported",
        "Under Inspection",
        "Maintenance",
        "Ready",
        "Resolved",
    }

    if new_status not in allowed_statuses:

        flash(
            "Invalid maintenance status.",
            "error",
        )

        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    connection = get_db()

    try:

        connection.execute(
            "BEGIN IMMEDIATE"
        )

        report = connection.execute(
            """
            SELECT
                report_id,
                bike_id,
                status

            FROM maintenance_reports

            WHERE report_id = ?
            """,
            (
                report_id,
            ),
        ).fetchone()

        if not report:

            connection.rollback()

            flash(
                "Maintenance report not found.",
                "error",
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        bike = connection.execute(
            """
            SELECT
                bike_id,
                status,
                station,
                slot

            FROM bikes

            WHERE bike_id = ?
            """,
            (
                report["bike_id"],
            ),
        ).fetchone()

        timestamp = now_ist()

        # ---------------------------------------------
        # UPDATE REPORT
        # ---------------------------------------------

        if new_status == "Resolved":

            connection.execute(
                """
                UPDATE maintenance_reports

                SET
                    status = 'Resolved',
                    resolved_at = ?

                WHERE report_id = ?
                """,
                (
                    timestamp,
                    report_id,
                ),
            )

        else:

            connection.execute(
                """
                UPDATE maintenance_reports

                SET
                    status = ?,
                    resolved_at = NULL

                WHERE report_id = ?
                """,
                (
                    new_status,
                    report_id,
                ),
            )

        # ---------------------------------------------
        # BIKE STATE
        # ---------------------------------------------

        if bike:

            # Reported / inspection / maintenance:
            # bike stays unavailable.
            if new_status in {
                "Reported",
                "Under Inspection",
                "Maintenance",
            }:

                if bike["status"] != "In use":

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
                            timestamp,
                            bike["bike_id"],
                        ),
                    )

            # Ready means repaired but not yet released.
            elif new_status == "Ready":

                if bike["status"] != "In use":

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
                            timestamp,
                            bike["bike_id"],
                        ),
                    )

            # Resolved returns the bike to service only
            # if NO other unresolved reports remain.
            elif new_status == "Resolved":

                other_open_report = connection.execute(
                    """
                    SELECT report_id

                    FROM maintenance_reports

                    WHERE bike_id = ?
                      AND status != 'Resolved'
                      AND resolved_at IS NULL

                    LIMIT 1
                    """,
                    (
                        bike["bike_id"],
                    ),
                ).fetchone()


                if other_open_report:

                    # Another problem is still open,
                    # so the bike must remain unavailable.
                    if bike["status"] != "In use":

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
                                timestamp,
                                bike["bike_id"],
                            ),
                        )


                elif (
                    bike["status"] != "In use"
                    and bike["station"]
                    and bike["slot"]
                ):

                    # All reports are resolved and the
                    # bike is safely parked.
                    connection.execute(
                        """
                        UPDATE bikes

                        SET
                            status = 'Available',
                            current_user = NULL,
                            lock_status = 'Locked',
                            location = station,
                            last_updated = ?

                        WHERE bike_id = ?
                        """,
                        (
                            timestamp,
                            bike["bike_id"],
                        ),
                    )

        connection.commit()

        flash(
            f"Report #{report_id} updated to {new_status}.",
            "success",
        )

    except sqlite3.Error as error:

        connection.rollback()

        print(
            "Maintenance admin error:",
            error,
        )

        flash(
            "Could not update maintenance report.",
            "error",
        )

    finally:

        connection.close()

    return redirect(
        url_for(
            "admin_dashboard"
        )
    )


# =========================================================
# ADMIN BIKE REBALANCING - START
# =========================================================

@app.route(
    "/admin/fleet/<bike_id>/rebalance",
    methods=["POST"],
)
@admin_required
def admin_rebalance_bike(
    bike_id
):

    bike_id = (
        bike_id
        .strip()
        .upper()
    )


    destination_text = (
        request.form.get(
            "destination_station_id",
            "",
        )
        .strip()
    )


    try:

        destination_station_id = int(
            destination_text
        )

    except ValueError:

        flash(
            "Choose a valid destination station.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard")
            + "#fleet"
        )


    connection = get_db()


    try:

        ensure_bike_movements_schema(
            connection
        )

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        # -------------------------------------------------
        # BIKE
        # -------------------------------------------------

        bike = connection.execute(
            """
            SELECT

                bike_id,
                status,
                current_user,
                station_id,
                station,
                slot

            FROM bikes

            WHERE
                bike_id = ?

                AND

                COALESCE(
                    active,
                    1
                ) = 1
            """,
            (
                bike_id,
            ),
        ).fetchone()


        if not bike:

            raise ValueError(
                "Bike not found."
            )


        if bike["status"] != "Available":

            raise ValueError(
                f"{bike_id} cannot start rebalancing "
                f"while its status is {bike['status']}."
            )


        if bike["current_user"]:

            raise ValueError(
                f"{bike_id} is assigned to a student."
            )


        if (
            bike["station_id"] is None
            or
            not bike["slot"]
        ):

            raise ValueError(
                f"{bike_id} is not currently "
                "recorded in a valid dock."
            )


        # -------------------------------------------------
        # SOURCE STATION
        # -------------------------------------------------

        source = connection.execute(
            """
            SELECT

                station_id,
                station_name,
                campus_id,
                display_name,
                sponsor_name

            FROM stations

            WHERE station_id = ?
            """,
            (
                bike["station_id"],
            ),
        ).fetchone()


        if not source:

            raise ValueError(
                "Source station could not be found."
            )


        # -------------------------------------------------
        # DESTINATION STATION
        # -------------------------------------------------

        destination = connection.execute(
            """
            SELECT

                station_id,
                station_name,
                campus_id,
                display_name,
                sponsor_name

            FROM stations

            WHERE
                station_id = ?

                AND

                COALESCE(
                    active,
                    1
                ) = 1
            """,
            (
                destination_station_id,
            ),
        ).fetchone()


        if not destination:

            raise ValueError(
                "Destination station is unavailable."
            )


        if (
            source["campus_id"]
            !=
            destination["campus_id"]
        ):

            raise ValueError(
                "A rebalancing move cannot cross campuses."
            )


        if (
            source["station_id"]
            ==
            destination["station_id"]
        ):

            raise ValueError(
                "Choose a different destination station."
            )


        # -------------------------------------------------
        # VERIFY SOURCE DOCK
        # -------------------------------------------------

        source_slot = connection.execute(
            """
            SELECT

                slot_id,
                slot_number

            FROM slots

            WHERE
                station_id = ?

                AND
                bike_id = ?

                AND
                status = 'Occupied'

            LIMIT 1
            """,
            (
                source["station_id"],
                bike_id,
            ),
        ).fetchone()


        if not source_slot:

            raise ValueError(
                "Source dock data is inconsistent. "
                "Movement cancelled."
            )


        # -------------------------------------------------
        # CHOOSE + RESERVE DESTINATION DOCK
        # -------------------------------------------------

        destination_slot = (
            connection.execute(
                """
                SELECT

                    slot_id,
                    slot_number

                FROM slots

                WHERE
                    station_id = ?

                    AND
                    status = 'Available'

                    AND
                    bike_id IS NULL

                ORDER BY
                    slot_id

                LIMIT 1
                """,
                (
                    destination[
                        "station_id"
                    ],
                ),
            ).fetchone()
        )


        if not destination_slot:

            raise ValueError(
                "Destination station has no free dock."
            )


        # -------------------------------------------------
        # PUBLIC NAMES
        # -------------------------------------------------

        source_display = (
            source["display_name"]
            or
            source["station_name"]
        )


        destination_display = (
            destination["display_name"]
            or
            destination["station_name"]
        )


        source_public = (
            f"{source['sponsor_name']} "
            f"{source_display}"
            if source["sponsor_name"]
            else source_display
        )


        destination_public = (
            f"{destination['sponsor_name']} "
            f"{destination_display}"
            if destination["sponsor_name"]
            else destination_display
        )


        timestamp = now_ist()


        # -------------------------------------------------
        # RELEASE SOURCE DOCK
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE slots

            SET
                bike_id = NULL,
                status = 'Available'

            WHERE slot_id = ?
            """,
            (
                source_slot[
                    "slot_id"
                ],
            ),
        )


        # -------------------------------------------------
        # RESERVE DESTINATION DOCK
        # -------------------------------------------------

        cursor = connection.execute(
            """
            UPDATE slots

            SET
                bike_id = ?,
                status = 'Reserved'

            WHERE
                slot_id = ?

                AND
                status = 'Available'

                AND
                bike_id IS NULL
            """,
            (
                bike_id,

                destination_slot[
                    "slot_id"
                ],
            ),
        )


        if cursor.rowcount != 1:

            raise ValueError(
                "Destination dock could not be reserved."
            )


        # -------------------------------------------------
        # BIKE IN TRANSIT
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE bikes

            SET
                status = 'Rebalancing',
                current_user = NULL,

                station = NULL,
                station_id = NULL,
                slot = NULL,
                location = NULL,

                lock_status = 'Unlocked',
                last_updated = ?

            WHERE bike_id = ?
            """,
            (
                timestamp,
                bike_id,
            ),
        )


        # -------------------------------------------------
        # MOVEMENT LOG
        # -------------------------------------------------

        connection.execute(
            """
            INSERT INTO bike_movements (

                bike_id,
                movement_type,

                from_station_id,
                from_station_name,
                from_slot,

                to_station_id,
                to_station_name,
                to_slot,

                admin_username,

                moved_at,
                movement_status,
                started_at,
                completed_at
            )

            VALUES (
                ?,
                'Rebalancing',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                'In Transit',
                ?,
                NULL
            )
            """,
            (
                bike_id,

                source[
                    "station_id"
                ],

                source_public,

                source_slot[
                    "slot_number"
                ],

                destination[
                    "station_id"
                ],

                destination_public,

                destination_slot[
                    "slot_number"
                ],

                session.get(
                    "admin_username",
                    "admin",
                ),

                timestamp,
                timestamp,
            ),
        )


        connection.commit()


        flash(
            (
                f"Rebalancing started for {bike_id}. "
                f"{destination_public} · "
                f"{destination_slot['slot_number']} "
                "has been reserved."
            ),
            "success",
        )


    except ValueError as error:

        connection.rollback()

        flash(
            str(error),
            "error",
        )


    except sqlite3.Error as error:

        connection.rollback()

        print(
            "Start rebalancing error:",
            error,
        )

        flash(
            "Could not start rebalancing.",
            "error",
        )


    finally:

        connection.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
        +
        "#fleet"
    )



# =========================================================
# ADMIN BIKE REBALANCING - COMPLETE
# =========================================================

@app.route(
    "/admin/fleet/<bike_id>/rebalance/complete",
    methods=["POST"],
)
@admin_required
def admin_complete_rebalance_bike(
    bike_id
):

    bike_id = (
        bike_id
        .strip()
        .upper()
    )


    connection = get_db()


    try:

        ensure_bike_movements_schema(
            connection
        )

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        # -------------------------------------------------
        # BIKE
        # -------------------------------------------------

        bike = connection.execute(
            """
            SELECT

                bike_id,
                status,
                current_user

            FROM bikes

            WHERE
                bike_id = ?

                AND

                COALESCE(
                    active,
                    1
                ) = 1
            """,
            (
                bike_id,
            ),
        ).fetchone()


        if not bike:

            raise ValueError(
                "Bike not found."
            )


        if bike["status"] != "Rebalancing":

            raise ValueError(
                f"{bike_id} is not currently "
                "being rebalanced."
            )


        # -------------------------------------------------
        # ACTIVE MOVEMENT
        # -------------------------------------------------

        movement = connection.execute(
            """
            SELECT

                movement_id,

                from_station_id,
                from_station_name,
                from_slot,

                to_station_id,
                to_station_name,
                to_slot,

                started_at

            FROM bike_movements

            WHERE
                bike_id = ?

                AND

                movement_status =
                    'In Transit'

            ORDER BY
                movement_id DESC

            LIMIT 1
            """,
            (
                bike_id,
            ),
        ).fetchone()


        if not movement:

            raise ValueError(
                "No active rebalancing movement "
                "was found."
            )


        # -------------------------------------------------
        # DESTINATION
        # -------------------------------------------------

        destination = connection.execute(
            """
            SELECT

                station_id,
                station_name,
                campus_id,
                display_name,
                sponsor_name

            FROM stations

            WHERE
                station_id = ?

                AND

                COALESCE(
                    active,
                    1
                ) = 1
            """,
            (
                movement[
                    "to_station_id"
                ],
            ),
        ).fetchone()


        if not destination:

            raise ValueError(
                "Reserved destination station "
                "is unavailable."
            )


        # -------------------------------------------------
        # VERIFY RESERVED DOCK
        # -------------------------------------------------

        reserved_slot = connection.execute(
            """
            SELECT

                slot_id,
                slot_number,
                status,
                bike_id

            FROM slots

            WHERE
                station_id = ?

                AND
                slot_number = ?

                AND
                status = 'Reserved'

                AND
                bike_id = ?

            LIMIT 1
            """,
            (
                movement[
                    "to_station_id"
                ],

                movement[
                    "to_slot"
                ],

                bike_id,
            ),
        ).fetchone()


        if not reserved_slot:

            raise ValueError(
                "The reserved destination dock "
                "could not be verified."
            )


        timestamp = now_ist()


        # -------------------------------------------------
        # RESERVED -> OCCUPIED
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE slots

            SET
                status = 'Occupied'

            WHERE
                slot_id = ?

                AND
                bike_id = ?

                AND
                status = 'Reserved'
            """,
            (
                reserved_slot[
                    "slot_id"
                ],

                bike_id,
            ),
        )


        # -------------------------------------------------
        # BIKE AVAILABLE AGAIN
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE bikes

            SET
                status = 'Available',
                current_user = NULL,

                station = ?,
                station_id = ?,
                slot = ?,
                location = ?,

                lock_status = 'Locked',
                last_updated = ?

            WHERE bike_id = ?
            """,
            (
                destination[
                    "station_name"
                ],

                destination[
                    "station_id"
                ],

                reserved_slot[
                    "slot_number"
                ],

                destination[
                    "station_name"
                ],

                timestamp,

                bike_id,
            ),
        )


        # -------------------------------------------------
        # COMPLETE LOG
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE bike_movements

            SET
                movement_status =
                    'Completed',

                completed_at = ?,
                moved_at = ?

            WHERE movement_id = ?
            """,
            (
                timestamp,
                timestamp,

                movement[
                    "movement_id"
                ],
            ),
        )


        connection.commit()


        flash(
            (
                f"{bike_id} rebalancing completed at "
                f"{movement['to_station_name']} · "
                f"{reserved_slot['slot_number']}."
            ),
            "success",
        )


    except ValueError as error:

        connection.rollback()

        flash(
            str(error),
            "error",
        )


    except sqlite3.Error as error:

        connection.rollback()

        print(
            "Complete rebalancing error:",
            error,
        )

        flash(
            "Could not complete rebalancing.",
            "error",
        )


    finally:

        connection.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
        +
        "#fleet"
    )


# =========================================================
# ADMIN BIKE REBALANCING - CANCEL / RETURN TO SOURCE
# =========================================================

@app.route(
    "/admin/fleet/<bike_id>/rebalance/cancel",
    methods=["POST"],
)
@admin_required
def admin_cancel_rebalance_bike(
    bike_id
):

    bike_id = (
        bike_id
        .strip()
        .upper()
    )


    connection = get_db()


    try:

        ensure_bike_movements_schema(
            connection
        )

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        # -------------------------------------------------
        # BIKE MUST CURRENTLY BE IN TRANSIT
        # -------------------------------------------------

        bike = connection.execute(
            """
            SELECT
                bike_id,
                status,
                current_user

            FROM bikes

            WHERE
                bike_id = ?

                AND

                COALESCE(
                    active,
                    1
                ) = 1
            """,
            (
                bike_id,
            ),
        ).fetchone()


        if not bike:

            raise ValueError(
                "Bike not found."
            )


        if bike["status"] != "Rebalancing":

            raise ValueError(
                f"{bike_id} is not currently "
                "being rebalanced."
            )


        # -------------------------------------------------
        # ACTIVE MOVEMENT
        # -------------------------------------------------

        movement = connection.execute(
            """
            SELECT
                movement_id,

                from_station_id,
                from_station_name,
                from_slot,

                to_station_id,
                to_station_name,
                to_slot

            FROM bike_movements

            WHERE
                bike_id = ?

                AND

                movement_status = 'In Transit'

            ORDER BY
                movement_id DESC

            LIMIT 1
            """,
            (
                bike_id,
            ),
        ).fetchone()


        if not movement:

            raise ValueError(
                "No active rebalancing movement was found."
            )


        # -------------------------------------------------
        # ORIGINAL SOURCE STATION
        # -------------------------------------------------

        source = connection.execute(
            """
            SELECT
                station_id,
                station_name,
                active

            FROM stations

            WHERE station_id = ?
            """,
            (
                movement[
                    "from_station_id"
                ],
            ),
        ).fetchone()


        if (
            not source
            or
            source["active"] != 1
        ):

            raise ValueError(
                "The original source station is unavailable. "
                "Complete the move at the reserved destination instead."
            )


        # -------------------------------------------------
        # SOURCE DOCK MUST STILL BE FREE
        # -------------------------------------------------
        #
        # We never pretend the bike returned to its source
        # if another bike has already taken that dock.
        # -------------------------------------------------

        source_slot = connection.execute(
            """
            SELECT
                slot_id,
                slot_number

            FROM slots

            WHERE
                station_id = ?

                AND
                slot_number = ?

                AND
                status = 'Available'

                AND
                bike_id IS NULL

            LIMIT 1
            """,
            (
                movement[
                    "from_station_id"
                ],

                movement[
                    "from_slot"
                ],
            ),
        ).fetchone()


        if not source_slot:

            raise ValueError(
                "Cannot safely cancel this move because the "
                "original source dock is no longer free. "
                "Complete the move at the reserved destination instead."
            )


        # -------------------------------------------------
        # RESERVED DESTINATION DOCK MUST STILL BELONG
        # TO THIS BIKE
        # -------------------------------------------------

        reserved_slot = connection.execute(
            """
            SELECT
                slot_id,
                slot_number

            FROM slots

            WHERE
                station_id = ?

                AND
                slot_number = ?

                AND
                status = 'Reserved'

                AND
                bike_id = ?

            LIMIT 1
            """,
            (
                movement[
                    "to_station_id"
                ],

                movement[
                    "to_slot"
                ],

                bike_id,
            ),
        ).fetchone()


        if not reserved_slot:

            raise ValueError(
                "The reserved destination dock could not be verified. "
                "No cancellation was made."
            )


        timestamp = now_ist()


        # -------------------------------------------------
        # RELEASE DESTINATION RESERVATION
        # -------------------------------------------------

        cursor = connection.execute(
            """
            UPDATE slots

            SET
                bike_id = NULL,
                status = 'Available'

            WHERE
                slot_id = ?

                AND
                bike_id = ?

                AND
                status = 'Reserved'
            """,
            (
                reserved_slot[
                    "slot_id"
                ],
                bike_id,
            ),
        )


        if cursor.rowcount != 1:

            raise ValueError(
                "The destination reservation changed before "
                "it could be released."
            )


        # -------------------------------------------------
        # RESTORE ORIGINAL SOURCE DOCK
        # -------------------------------------------------

        cursor = connection.execute(
            """
            UPDATE slots

            SET
                bike_id = ?,
                status = 'Occupied'

            WHERE
                slot_id = ?

                AND
                status = 'Available'

                AND
                bike_id IS NULL
            """,
            (
                bike_id,

                source_slot[
                    "slot_id"
                ],
            ),
        )


        if cursor.rowcount != 1:

            raise ValueError(
                "The original source dock was just taken. "
                "No cancellation was made."
            )


        # -------------------------------------------------
        # RESTORE BIKE TO SOURCE
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE bikes

            SET
                status = 'Available',
                current_user = NULL,

                station = ?,
                station_id = ?,
                slot = ?,
                location = ?,

                lock_status = 'Locked',
                last_updated = ?

            WHERE bike_id = ?
            """,
            (
                source[
                    "station_name"
                ],

                source[
                    "station_id"
                ],

                source_slot[
                    "slot_number"
                ],

                source[
                    "station_name"
                ],

                timestamp,
                bike_id,
            ),
        )


        # -------------------------------------------------
        # CANCEL MOVEMENT LOG
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE bike_movements

            SET
                movement_status = 'Cancelled',
                completed_at = ?,
                moved_at = ?

            WHERE
                movement_id = ?

                AND
                movement_status = 'In Transit'
            """,
            (
                timestamp,
                timestamp,

                movement[
                    "movement_id"
                ],
            ),
        )


        connection.commit()


        flash(
            (
                f"Rebalancing cancelled for {bike_id}. "
                f"Bike restored to "
                f"{movement['from_station_name']} · "
                f"{source_slot['slot_number']}."
            ),
            "success",
        )


    except ValueError as error:

        connection.rollback()

        flash(
            str(error),
            "error",
        )


    except sqlite3.Error as error:

        connection.rollback()

        print(
            "Cancel rebalancing error:",
            error,
        )

        flash(
            "Could not cancel rebalancing.",
            "error",
        )


    finally:

        connection.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
        +
        "#fleet"
    )


# =========================================================
# API - CAMPUS SERVICE AREA
# =========================================================

@app.route(
    "/api/campus-boundary"
)
def api_campus_boundary():

    connection = get_db()


    campus = connection.execute(
        """
        SELECT
            campus_id,
            campus_name,
            city,
            latitude,
            longitude

        FROM campuses

        WHERE active = 1

        ORDER BY campus_id

        LIMIT 1
        """
    ).fetchone()


    if not campus:

        connection.close()

        return {
            "campus": None,
            "points": [],
        }, 404


    rows = connection.execute(
        """
        SELECT
            point_order,
            latitude,
            longitude

        FROM campus_boundary_points

        WHERE campus_id = ?

        ORDER BY point_order
        """,
        (
            campus["campus_id"],
        ),
    ).fetchall()


    points = [

        {
            "latitude":
                row["latitude"],

            "longitude":
                row["longitude"],
        }

        for row in rows

    ]


    result = {

        "campus": {
            "campus_id":
                campus["campus_id"],

            "campus_name":
                campus["campus_name"],

            "city":
                campus["city"],

            "latitude":
                campus["latitude"],

            "longitude":
                campus["longitude"],
        },

        "points":
            points,
    }


    connection.close()


    return result


# =========================================================
# ADMIN CAMPUS SERVICE AREA
# =========================================================

@app.route(
    "/admin/campus-boundary",
    methods=["GET", "POST"],
)
@admin_required
def admin_campus_boundary():

    connection = get_db()


    # -----------------------------------------------------
    # CURRENT ACTIVE CAMPUS
    # -----------------------------------------------------

    campus = connection.execute(
        """
        SELECT
            campus_id,
            campus_name,
            city,
            latitude,
            longitude

        FROM campuses

        WHERE active = 1

        ORDER BY campus_id

        LIMIT 1
        """
    ).fetchone()


    if not campus:

        connection.close()

        flash(
            "No active campus exists.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard")
        )


    campus_id = campus["campus_id"]


    # -----------------------------------------------------
    # SAVE BOUNDARY
    # -----------------------------------------------------

    if request.method == "POST":

        boundary_json = request.form.get(
            "boundary_json",
            "",
        ).strip()


        try:

            raw_points = json.loads(
                boundary_json
            )


            if not isinstance(
                raw_points,
                list,
            ):

                raise ValueError(
                    "Invalid boundary."
                )


            if len(raw_points) < 3:

                raise ValueError(
                    "A campus boundary needs at least 3 points."
                )


            if len(raw_points) > 200:

                raise ValueError(
                    "Campus boundary has too many points."
                )


            clean_points = []


            for point in raw_points:

                latitude = float(
                    point["latitude"]
                )

                longitude = float(
                    point["longitude"]
                )


                if not -90 <= latitude <= 90:

                    raise ValueError(
                        "Invalid latitude."
                    )


                if not -180 <= longitude <= 180:

                    raise ValueError(
                        "Invalid longitude."
                    )


                clean_points.append({
                    "latitude":
                        latitude,

                    "longitude":
                        longitude,
                })


        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:

            connection.close()

            flash(
                str(error)
                or
                "Invalid campus boundary.",
                "error",
            )

            return redirect(
                url_for(
                    "admin_campus_boundary"
                )
            )


        try:

            connection.execute(
                "BEGIN IMMEDIATE"
            )


            # Replace previous polygon.

            connection.execute(
                """
                DELETE FROM
                    campus_boundary_points

                WHERE campus_id = ?
                """,
                (
                    campus_id,
                ),
            )


            for index, point in enumerate(
                clean_points,
                start=1,
            ):

                connection.execute(
                    """
                    INSERT INTO
                        campus_boundary_points (
                            campus_id,
                            point_order,
                            latitude,
                            longitude
                        )

                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        campus_id,
                        index,
                        point["latitude"],
                        point["longitude"],
                    ),
                )


            # Store approximate campus centre.

            centre_latitude = (
                sum(
                    point["latitude"]
                    for point in clean_points
                )
                /
                len(clean_points)
            )


            centre_longitude = (
                sum(
                    point["longitude"]
                    for point in clean_points
                )
                /
                len(clean_points)
            )


            connection.execute(
                """
                UPDATE campuses

                SET
                    latitude = ?,
                    longitude = ?

                WHERE campus_id = ?
                """,
                (
                    centre_latitude,
                    centre_longitude,
                    campus_id,
                ),
            )


            connection.commit()


        except sqlite3.Error as error:

            connection.rollback()

            print(
                "Campus boundary save error:",
                error,
            )

            connection.close()

            flash(
                "Could not save campus service area.",
                "error",
            )

            return redirect(
                url_for(
                    "admin_campus_boundary"
                )
            )


        connection.close()


        flash(
            f"Campus service area saved with {len(clean_points)} boundary points.",
            "success",
        )


        return redirect(
            url_for(
                "admin_campus_boundary"
            )
        )


    # -----------------------------------------------------
    # LOAD CURRENT BOUNDARY
    # -----------------------------------------------------

    rows = connection.execute(
        """
        SELECT
            point_order,
            latitude,
            longitude

        FROM campus_boundary_points

        WHERE campus_id = ?

        ORDER BY point_order
        """,
        (
            campus_id,
        ),
    ).fetchall()


    boundary_points = [

        {
            "latitude":
                row["latitude"],

            "longitude":
                row["longitude"],
        }

        for row in rows

    ]


    # -----------------------------------------------------
    # MAP START POSITION
    # -----------------------------------------------------

    if boundary_points:

        map_center = {
            "latitude":
                sum(
                    point["latitude"]
                    for point in boundary_points
                )
                /
                len(boundary_points),

            "longitude":
                sum(
                    point["longitude"]
                    for point in boundary_points
                )
                /
                len(boundary_points),
        }


    elif (
        campus["latitude"] is not None
        and
        campus["longitude"] is not None
    ):

        map_center = {
            "latitude":
                campus["latitude"],

            "longitude":
                campus["longitude"],
        }


    else:

        station = connection.execute(
            """
            SELECT
                latitude,
                longitude

            FROM stations

            WHERE campus_id = ?
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL

            ORDER BY station_id

            LIMIT 1
            """,
            (
                campus_id,
            ),
        ).fetchone()


        if station:

            map_center = {
                "latitude":
                    station["latitude"],

                "longitude":
                    station["longitude"],
            }

        else:

            # General India fallback.
            # Admin can press "My location".
            map_center = {
                "latitude": 20.5937,
                "longitude": 78.9629,
            }


    connection.close()


    return render_template(
        "admin_campus_boundary.html",

        campus=
            campus,

        boundary_points=
            boundary_points,

        map_center=
            map_center,
    )


# =========================================================
# ADMIN STATION SETTINGS
# =========================================================

@app.route(
    "/admin/stations/<int:station_id>/settings",
    methods=["POST"],
)
@admin_required
def admin_station_settings(station_id):

    display_name = request.form.get(
        "display_name",
        "",
    ).strip()

    sponsor_name = request.form.get(
        "sponsor_name",
        "",
    ).strip()

    latitude_text = request.form.get(
        "latitude",
        "",
    ).strip()

    longitude_text = request.form.get(
        "longitude",
        "",
    ).strip()


    if not display_name:

        flash(
            "Station display name cannot be empty.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard") + "#stations"
        )


    latitude = None
    longitude = None


    if latitude_text or longitude_text:

        if not latitude_text or not longitude_text:

            flash(
                "Enter both latitude and longitude.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


        try:

            latitude = float(latitude_text)
            longitude = float(longitude_text)

        except ValueError:

            flash(
                "Latitude and longitude must be valid numbers.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


        if not -90 <= latitude <= 90:

            flash(
                "Latitude must be between -90 and 90.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


        if not -180 <= longitude <= 180:

            flash(
                "Longitude must be between -180 and 180.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


    connection = get_db()


    station = connection.execute(
        """
        SELECT
            station_id,
            station_name
        FROM stations
        WHERE station_id = ?
        """,
        (
            station_id,
        ),
    ).fetchone()


    if not station:

        connection.close()

        flash(
            "Station not found.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard") + "#stations"
        )


    connection.execute(
        """
        UPDATE stations

        SET
            display_name = ?,
            sponsor_name = ?,
            latitude = ?,
            longitude = ?

        WHERE station_id = ?
        """,
        (
            display_name,
            sponsor_name or None,
            latitude,
            longitude,
            station_id,
        ),
    )


    connection.commit()
    connection.close()


    public_name = (
        f"{sponsor_name} {display_name}"
        if sponsor_name
        else display_name
    )


    flash(
        f"{public_name} station settings saved.",
        "success",
    )


    return redirect(
        url_for("admin_dashboard") + "#stations"
    )


# =========================================================
# ADMIN CREATE STATION
# =========================================================

@app.route(
    "/admin/stations/create",
    methods=["POST"],
)
@admin_required
def admin_create_station():

    display_name = request.form.get(
        "display_name",
        "",
    ).strip()

    sponsor_name = request.form.get(
        "sponsor_name",
        "",
    ).strip()

    total_slots_text = request.form.get(
        "total_slots",
        "4",
    ).strip()

    latitude_text = request.form.get(
        "latitude",
        "",
    ).strip()

    longitude_text = request.form.get(
        "longitude",
        "",
    ).strip()


    # -----------------------------------------------------
    # DISPLAY NAME
    # -----------------------------------------------------

    if not display_name:

        flash(
            "Station display name is required.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard") + "#stations"
        )


    # -----------------------------------------------------
    # NUMBER OF DOCKS
    # -----------------------------------------------------

    try:

        total_slots = int(
            total_slots_text
        )

    except ValueError:

        flash(
            "Number of docks must be a whole number.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard") + "#stations"
        )


    if total_slots < 1 or total_slots > 100:

        flash(
            "A station must have between 1 and 100 docks.",
            "error",
        )

        return redirect(
            url_for("admin_dashboard") + "#stations"
        )


    # -----------------------------------------------------
    # GPS
    # -----------------------------------------------------

    latitude = None
    longitude = None


    if latitude_text or longitude_text:

        if not latitude_text or not longitude_text:

            flash(
                "Enter both latitude and longitude.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


        try:

            latitude = float(
                latitude_text
            )

            longitude = float(
                longitude_text
            )

        except ValueError:

            flash(
                "Latitude and longitude must be valid numbers.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


        if not -90 <= latitude <= 90:

            flash(
                "Latitude must be between -90 and 90.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


        if not -180 <= longitude <= 180:

            flash(
                "Longitude must be between -180 and 180.",
                "error",
            )

            return redirect(
                url_for("admin_dashboard") + "#stations"
            )


    connection = get_db()


    try:

        connection.execute(
            "BEGIN IMMEDIATE"
        )


        # -------------------------------------------------
        # CREATE TEMPORARY STATION
        # -------------------------------------------------

        cursor = connection.execute(
            """
            INSERT INTO stations (
                station_name,
                display_name,
                sponsor_name,
                total_slots,
                active,
                campus_id,
                latitude,
                longitude
            )

            VALUES (
                ?,
                ?,
                ?,
                ?,
                1,
                1,
                ?,
                ?
            )
            """,
            (
                f"TEMP-{now_ist()}",
                display_name,
                sponsor_name or None,
                total_slots,
                latitude,
                longitude,
            ),
        )


        station_id = cursor.lastrowid

        station_code = (
            f"STN{station_id:03d}"
        )


        # -------------------------------------------------
        # PERMANENT BACKEND IDENTITY
        # -------------------------------------------------

        connection.execute(
            """
            UPDATE stations

            SET
                station_name = ?,
                station_code = ?

            WHERE station_id = ?
            """,
            (
                station_code,
                station_code,
                station_id,
            ),
        )


        # -------------------------------------------------
        # CREATE DOCKS
        # -------------------------------------------------

        for slot_number in range(
            1,
            total_slots + 1
        ):

            slot_name = (
                f"SLOT-{slot_number:02d}"
            )


            connection.execute(
                """
                INSERT INTO slots (
                    station_name,
                    station_id,
                    slot_number,
                    bike_id,
                    status
                )

                VALUES (
                    ?,
                    ?,
                    ?,
                    NULL,
                    'Available'
                )
                """,
                (
                    station_code,
                    station_id,
                    slot_name,
                ),
            )


        connection.commit()


    except sqlite3.Error as error:

        connection.rollback()

        print(
            "Create station error:",
            error,
        )

        flash(
            "Could not create station.",
            "error",
        )

        connection.close()

        return redirect(
            url_for("admin_dashboard") + "#stations"
        )


    connection.close()


    public_name = (
        f"{sponsor_name} {display_name}"
        if sponsor_name
        else display_name
    )


    flash(
        f"{public_name} created with {total_slots} docks.",
        "success",
    )


    return redirect(
        url_for("admin_dashboard") + "#stations"
    )


# =========================================================
# ADMIN QR LABEL PAGE
# =========================================================

@app.route(
    "/admin/qr"
)

@admin_required

def admin_qr_labels():

    connection = get_db()


    bikes = connection.execute(

        """
        SELECT
            bike_id

        FROM bikes

        WHERE
            COALESCE(
                active,
                1
            ) = 1

        ORDER BY
            bike_id
        """

    ).fetchall()


    connection.close()


    return render_template(

        "admin_qr.html",

        bikes=
            bikes,

        qr_version=
            int(
                datetime.now().timestamp()
            ),

    )


# =========================================================
# ADMIN QR IMAGE
# =========================================================

@app.route(
    "/admin/qr/<bike_id>.png"
)

@admin_required

def admin_qr_png(
    bike_id
):

    connection = get_db()


    bike = connection.execute(

        """
        SELECT

            bike_id,
            qr_secret

        FROM bikes

        WHERE
            bike_id = ?

            AND

            COALESCE(
                active,
                1
            ) = 1
        """,

        (
            bike_id.upper(),
        ),

    ).fetchone()


    connection.close()


    if not bike:

        abort(404)


    image = qrcode.make(
        qr_payload(
            bike
        )
    )


    buffer = io.BytesIO()


    image.save(
        buffer,
        format="PNG",
    )


    buffer.seek(0)


    response = send_file(

        buffer,

        mimetype=
            "image/png",

        download_name=
            f"{bike['bike_id']}-qr.png",

    )


    # Always serve the current bike QR.
    # Prevent browser/proxy caching of old QR images.
    response.headers[
        "Cache-Control"
    ] = (
        "no-store, no-cache, "
        "must-revalidate, max-age=0"
    )

    response.headers[
        "Pragma"
    ] = "no-cache"

    response.headers[
        "Expires"
    ] = "0"


    return response


# =========================================================
# HEALTH
# =========================================================

@app.route(
    "/health"
)

def health():

    return {
        "ok": True
    }


# =========================================================
# 404
# =========================================================

@app.errorhandler(
    404
)

def not_found(
    _error
):

    return render_template(

        "error.html",

        title=
            "Not found",

        message=
            "That CampusBike page does not exist.",

    ), 404


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    app.run(

        host=
            "0.0.0.0",

        port=
            5000,

        debug=
            True,

    )