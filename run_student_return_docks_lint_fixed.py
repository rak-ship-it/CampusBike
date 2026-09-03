import subprocess

import apply_student_return_docks as patch


# Make the end-ride station_id replacement specific to end_ride().
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


original_run = patch.run


def fixed_run(*args):
    if args == (
        "npx",
        "eslint",
        "app/(tabs)/ride.tsx",
    ):
        # The existing screen already had two unescaped JSX apostrophes,
        # and the new return confirmation adds one more. Fix all three
        # before linting so validation checks the final file that will
        # actually be committed.
        ride_path = patch.RIDE_PATH
        text = ride_path.read_text(encoding="utf-8")
        text = text.replace(
            "Couldn't load your ride",
            "Couldn&apos;t load your ride",
        )
        text = text.replace(
            "I've docked the bike",
            "I&apos;ve docked the bike",
        )
        text = text.replace(
            "You don't currently have a CampusBike checked out.",
            "You don&apos;t currently have a CampusBike checked out.",
        )
        ride_path.write_text(text, encoding="utf-8")

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
