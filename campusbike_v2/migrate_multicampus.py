import sqlite3

DB_NAME = "campusbike.db"

connection = sqlite3.connect(DB_NAME)
cursor = connection.cursor()


# =========================================================
# CREATE CAMPUSES TABLE
# =========================================================

cursor.execute("""
    CREATE TABLE IF NOT EXISTS campuses (
        campus_id INTEGER PRIMARY KEY AUTOINCREMENT,
        campus_name TEXT UNIQUE NOT NULL,
        city TEXT,
        latitude REAL,
        longitude REAL,
        active INTEGER DEFAULT 1
    )
""")


# =========================================================
# ADD MISSING COLUMNS TO STATIONS
# =========================================================

def add_column_if_missing(
    table_name,
    column_name,
    definition
):
    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    existing_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if column_name not in existing_columns:
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )


add_column_if_missing(
    "stations",
    "campus_id",
    "INTEGER"
)

add_column_if_missing(
    "stations",
    "latitude",
    "REAL"
)

add_column_if_missing(
    "stations",
    "longitude",
    "REAL"
)


# =========================================================
# CREATE FIRST CAMPUS
# =========================================================

cursor.execute("""
    INSERT OR IGNORE INTO campuses (
        campus_name,
        city,
        latitude,
        longitude,
        active
    )
    VALUES (
        'Campus 1',
        NULL,
        NULL,
        NULL,
        1
    )
""")


cursor.execute("""
    SELECT campus_id
    FROM campuses
    WHERE campus_name = 'Campus 1'
""")

campus_1_id = cursor.fetchone()[0]


# =========================================================
# ASSIGN EXISTING STATIONS TO CAMPUS 1
# =========================================================

cursor.execute("""
    UPDATE stations
    SET campus_id = ?
    WHERE campus_id IS NULL
""", (
    campus_1_id,
))


connection.commit()


# =========================================================
# SHOW RESULT
# =========================================================

print("\nCampuses:")
for row in cursor.execute("""
    SELECT
        campus_id,
        campus_name,
        city,
        latitude,
        longitude,
        active
    FROM campuses
"""):
    print(row)


print("\nStations:")
for row in cursor.execute("""
    SELECT
        station_id,
        station_name,
        total_slots,
        active,
        campus_id,
        latitude,
        longitude
    FROM stations
    ORDER BY station_id
"""):
    print(row)


connection.close()

print("\nMulti-campus migration complete.")