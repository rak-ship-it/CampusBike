from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
APP_PATH = ROOT / "campusbike_v2" / "app.py"
ADMIN_PATH = ROOT / "campusbike_v2" / "templates" / "admin.html"


APP_MARKER = """\n\n# =========================================================\n# API - CAMPUS SERVICE AREA\n# =========================================================\n"""


CANCEL_ROUTE = r'''

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
'''


COMPLETE_BUTTON_BLOCK = '''                                <button
                                    type="submit"
                                    class="rebalance-complete-button"
                                >
                                    Complete
                                </button>

                            </form>
'''


CANCEL_BUTTON_BLOCK = '''                                <button
                                    type="submit"
                                    class="rebalance-complete-button"
                                >
                                    Complete
                                </button>

                            </form>


                            <form
                                method="POST"
                                action="{{
                                    url_for(
                                        'admin_cancel_rebalance_bike',
                                        bike_id=bike.bike_id
                                    )
                                }}"
                                style="margin-top: 8px;"
                                onsubmit="
                                    return confirm(
                                        'Cancel only if the bike has been physically returned to its original source dock. Continue?'
                                    );
                                "
                            >

                                <input
                                    type="hidden"
                                    name="csrf_token"
                                    value="{{ csrf_token() }}"
                                >

                                <button
                                    type="submit"
                                    class="action-button red"
                                >
                                    Cancel move
                                </button>

                            </form>
'''


HISTORY_STATUS_BLOCK = '''                                {% if
                                    movement.movement_status
                                    ==
                                    'In Transit'
                                %}

                                    <span class="status status-use">
                                        In transit
                                    </span>

                                {% else %}

                                    <span class="status status-available">
                                        Completed
                                    </span>

                                {% endif %}
'''


HISTORY_STATUS_REPLACEMENT = '''                                {% if
                                    movement.movement_status
                                    ==
                                    'In Transit'
                                %}

                                    <span class="status status-use">
                                        In transit
                                    </span>

                                {% elif
                                    movement.movement_status
                                    ==
                                    'Cancelled'
                                %}

                                    <span class="status status-reported">
                                        Cancelled
                                    </span>

                                {% else %}

                                    <span class="status status-available">
                                        Completed
                                    </span>

                                {% endif %}
'''


def fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)


def run(*args):
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    if not APP_PATH.exists() or not ADMIN_PATH.exists():
        fail("Run this script from the CampusBike repository after git pull.")

    app_text = APP_PATH.read_text(encoding="utf-8")
    admin_text = ADMIN_PATH.read_text(encoding="utf-8")

    already_route = "def admin_cancel_rebalance_bike(" in app_text
    already_button = "'admin_cancel_rebalance_bike'" in admin_text
    already_history = "movement.movement_status\n                                    ==\n                                    'Cancelled'" in admin_text

    if already_route and already_button and already_history:
        print("Cancel rebalancing is already installed. Nothing to change.")
        return

    if already_route or already_button:
        fail(
            "A partial cancel-rebalancing patch already exists. "
            "Stop here so we can inspect it before changing anything."
        )

    if APP_MARKER not in app_text:
        fail("Could not find the campus-service-area marker in app.py.")

    if COMPLETE_BUTTON_BLOCK not in admin_text:
        fail("Could not find the Fleet Complete button block in admin.html.")

    if HISTORY_STATUS_BLOCK not in admin_text:
        fail("Could not find the rebalancing history status block in admin.html.")

    new_app = app_text.replace(
        APP_MARKER,
        CANCEL_ROUTE + APP_MARKER,
        1,
    )

    new_admin = admin_text.replace(
        COMPLETE_BUTTON_BLOCK,
        CANCEL_BUTTON_BLOCK,
        1,
    )

    new_admin = new_admin.replace(
        HISTORY_STATUS_BLOCK,
        HISTORY_STATUS_REPLACEMENT,
        1,
    )

    APP_PATH.write_text(new_app, encoding="utf-8")
    ADMIN_PATH.write_text(new_admin, encoding="utf-8")

    try:
        run("python3", "-m", "py_compile", "campusbike_v2/app.py")

        try:
            from jinja2 import Environment
            Environment().parse(new_admin)
            print("+ Jinja template syntax check passed")
        except ImportError:
            print("Jinja2 is not importable here; skipping template parser check.")

        run("git", "diff", "--check")

    except Exception:
        APP_PATH.write_text(app_text, encoding="utf-8")
        ADMIN_PATH.write_text(admin_text, encoding="utf-8")
        print("Patch validation failed; original files were restored.")
        raise

    print("\nPatch validated. Committing only the two changed application files...")

    run(
        "git",
        "add",
        "campusbike_v2/app.py",
        "campusbike_v2/templates/admin.html",
    )

    # Avoid accidentally including unrelated staged files.
    result = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--quiet",
            "--",
            "campusbike_v2/app.py",
            "campusbike_v2/templates/admin.html",
        ],
        cwd=ROOT,
    )

    if result.returncode == 0:
        print("No application changes need committing.")
        return

    run(
        "git",
        "commit",
        "--only",
        "campusbike_v2/app.py",
        "campusbike_v2/templates/admin.html",
        "-m",
        "Add safe cancel rebalancing recovery",
    )

    run("git", "push", "origin", "main")

    print("\nSUCCESS: Cancel rebalancing was added, validated, committed, and pushed.")
    print(
        "Safety rule: cancellation only succeeds when the original source dock "
        "is still free and the destination reservation still belongs to the bike."
    )


if __name__ == "__main__":
    main()
