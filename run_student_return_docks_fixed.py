import subprocess

import apply_student_return_docks as patch


# The original helper used a station_id snippet that also appears in the
# newly inserted reserve-return route, so its safety check correctly stopped
# instead of guessing. Make the target specific to end_ride().
patch.END_REQUEST_OLD = '''def end_ride():

    data = request.get_json(silent=True) or {}

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()

    station_id = data.get("station_id")
'''

patch.END_REQUEST_NEW = '''def end_ride():

    data = request.get_json(silent=True) or {}

    student_id = str(
        data.get("student_id", "")
    ).strip().upper()

    station_id = data.get("station_id")

    requested_slot = str(
        data.get("slot_number", "")
    ).strip().upper()
'''


# Run the existing Expo ESLint installation from the mobile-project folder.
original_run = patch.run


def fixed_run(*args):
    if args == (
        "npx",
        "eslint",
        "app/(tabs)/ride.tsx",
    ):
        print("+ cd CampusBikeMobile && npx eslint 'app/(tabs)/ride.tsx'")
        subprocess.run(
            ["npx", "eslint", "app/(tabs)/ride.tsx"],
            cwd=patch.ROOT / "CampusBikeMobile",
            check=True,
        )
        return

    original_run(*args)


patch.run = fixed_run


if __name__ == "__main__":
    patch.main()
