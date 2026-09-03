from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
API_PATH = ROOT / "campusbike_v2" / "mobile_api.py"
RIDE_PATH = ROOT / "CampusBikeMobile" / "app" / "(tabs)" / "ride.tsx"


def fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        fail(f"Expected exactly one {label}; found {count}.")
    return text.replace(old, new, 1)


def run(*args):
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


# =========================================================
# MOBILE API PATCHES
# =========================================================

ACTIVE_RIDE_OLD = '''    ride = cursor.fetchone()

    connection.close()


    if ride is None:

        return jsonify({
            "success": True,
            "active_ride": None
        })


    return jsonify({
        "success": True,
        "active_ride": dict(ride)
    })
'''


ACTIVE_RIDE_NEW = '''    ride = cursor.fetchone()


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
'''


END_RIDE_MARKER = '''# =========================================================
# END RIDE / RETURN BIKE
# =========================================================
'''


RETURN_ROUTES = r'''# =========================================================
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


'''


END_REQUEST_OLD = '''    station_id = data.get("station_id")
'''

END_REQUEST_NEW = '''    station_id = data.get("station_id")

    requested_slot = str(
        data.get("slot_number", "")
    ).strip().upper()
'''


SLOT_SELECTION_OLD = '''        # -------------------------------------------------
        # AUTOMATICALLY FIND FIRST FREE SLOT
        # USING PERMANENT station_id
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                slot_id,
                slot_number

            FROM slots

            WHERE station_id = ?
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
'''


SLOT_SELECTION_NEW = '''        # -------------------------------------------------
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
'''


OCCUPY_OLD = '''        cursor.execute("""
            UPDATE slots

            SET
                bike_id = ?,
                status = 'Occupied'

            WHERE slot_id = ?
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
                "message": "That slot was just taken. Please try again."
            }), 409
'''


OCCUPY_NEW = '''        if slot["status"] == "Reserved":

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
'''


# =========================================================
# RIDE SCREEN PATCHES
# =========================================================

ACTIVE_RIDE_TYPE_OLD = '''  current_user: string | null;
};


type Station = {
'''

ACTIVE_RIDE_TYPE_NEW = '''  current_user: string | null;

  reserved_return_station_id?: number | null;
  reserved_return_station?: string | null;
  reserved_return_slot?: string | null;
};


type ReturnReservation = {
  bike_id: string;
  station_id: number;
  station: string;
  slot: string;
};


type Station = {
'''


STATE_OLD = '''  const [selectedStation, setSelectedStation] =
    useState<Station | null>(null);

  const [error, setError] =
    useState('');
'''

STATE_NEW = '''  const [selectedStation, setSelectedStation] =
    useState<Station | null>(null);

  const [returnReservation, setReturnReservation] =
    useState<ReturnReservation | null>(null);

  const [error, setError] =
    useState('');
'''


LOAD_RIDE_OLD = '''      setRide(
        rideData.active_ride
      );


      if (stationResponse.ok) {
'''

LOAD_RIDE_NEW = '''      const activeRide: ActiveRide | null =
        rideData.active_ride;


      setRide(
        activeRide
      );


      if (
        activeRide?.reserved_return_station_id &&
        activeRide?.reserved_return_station &&
        activeRide?.reserved_return_slot
      ) {

        setReturnReservation({
          bike_id:
            activeRide.bike_id,

          station_id:
            activeRide.reserved_return_station_id,

          station:
            activeRide.reserved_return_station,

          slot:
            activeRide.reserved_return_slot,
        });

      } else {

        setReturnReservation(null);

      }


      if (stationResponse.ok) {
'''


END_FUNCTION_OLD = '''  async function endRide() {
'''

END_FUNCTION_NEW = '''  async function reserveReturnDock() {
'''


DIRECT_COMPLETE_OLD = '''      // =================================================
      // GPS CHECK PASSED — COMPLETE RETURN
      // =================================================

      const response = await fetch(
        `${API_BASE_URL}/api/end-ride`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify({

            student_id:
              student.student_id,

            station_id:
              selectedStation.station_id,

          }),

        }
      );


      const data =
        await response.json();


      if (
        !response.ok ||
        !data.success
      ) {

        Alert.alert(
          'Could not end ride',
          data.message ||
          'Please try again.'
        );

        return;

      }


      Alert.alert(
        'Ride complete',
        `${data.return.bike_id} returned to ${data.return.station}, ${data.return.slot}.`
      );


      setRide(null);

      setSelectedStation(null);

      setShowStations(false);


      await loadRide();
'''


DIRECT_COMPLETE_NEW = '''      // =================================================
      // GPS CHECK PASSED — RESERVE AN EXACT RETURN DOCK
      // =================================================

      const response = await fetch(
        `${API_BASE_URL}/api/reserve-return-slot`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify({

            student_id:
              student.student_id,

            station_id:
              selectedStation.station_id,

          }),

        }
      );


      const data =
        await response.json();


      if (
        !response.ok ||
        !data.success
      ) {

        if (data.reservation) {

          setReturnReservation(
            data.reservation
          );

        }

        Alert.alert(
          'Could not reserve dock',
          data.message ||
          'Please try again.'
        );

        return;

      }


      setReturnReservation(
        data.reservation
      );

      setShowStations(false);


      Alert.alert(
        'Return dock assigned',
        `Use ${data.reservation.slot} at ${data.reservation.station}. Put ${data.reservation.bike_id} into that numbered dock, then confirm in the app.`
      );
'''


NEW_FUNCTIONS_MARKER = '''  // =====================================================
  // LOADING
  // =====================================================
'''


NEW_FUNCTIONS = r'''  // =====================================================
  // CONFIRM BIKE IS IN THE ASSIGNED DOCK
  // =====================================================

  async function confirmDocked() {

    if (
      !student ||
      !returnReservation
    ) {
      return;
    }


    setEndingRide(true);


    try {

      const response = await fetch(
        `${API_BASE_URL}/api/end-ride`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify({
            student_id:
              student.student_id,

            station_id:
              returnReservation.station_id,

            slot_number:
              returnReservation.slot,
          }),
        }
      );


      const data =
        await response.json();


      if (
        !response.ok ||
        !data.success
      ) {

        Alert.alert(
          'Could not complete return',
          data.message ||
          'Please try again.'
        );

        return;

      }


      Alert.alert(
        'Ride complete',
        `${data.return.bike_id} is returned at ${data.return.station}, ${data.return.slot}.`
      );


      setRide(null);
      setReturnReservation(null);
      setSelectedStation(null);
      setShowStations(false);


      await loadRide();


    } catch (error) {

      console.log(
        'Confirm dock error:',
        error
      );

      Alert.alert(
        'Connection error',
        'Could not connect to CampusBike.'
      );

    } finally {

      setEndingRide(false);

    }

  }


  // =====================================================
  // CANCEL STUDENT RETURN DOCK ASSIGNMENT
  // =====================================================

  async function cancelReturnReservation() {

    if (!student) {
      return;
    }


    setEndingRide(true);


    try {

      const response = await fetch(
        `${API_BASE_URL}/api/cancel-return-slot`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify({
            student_id:
              student.student_id,
          }),
        }
      );


      const data =
        await response.json();


      if (
        !response.ok ||
        !data.success
      ) {

        Alert.alert(
          'Could not cancel assignment',
          data.message ||
          'Please try again.'
        );

        return;

      }


      setReturnReservation(null);
      setSelectedStation(null);
      setShowStations(true);

      await loadRide();


    } catch (error) {

      console.log(
        'Cancel return assignment error:',
        error
      );

      Alert.alert(
        'Connection error',
        'Could not connect to CampusBike.'
      );

    } finally {

      setEndingRide(false);

    }

  }


'''


RETURN_TERNARY_OLD = '''            {!showStations ? (
'''

RETURN_TERNARY_NEW = '''            {returnReservation ? (

              <View style={styles.returnCard}>

                <Text style={styles.smallLabel}>
                  ASSIGNED RETURN DOCK
                </Text>

                <Text style={styles.returnTitle}>
                  {returnReservation.station}
                </Text>


                <View
                  style={{
                    marginTop: 18,
                    marginBottom: 18,
                    paddingVertical: 22,
                    borderRadius: 18,
                    alignItems: 'center',
                    backgroundColor: '#FFF0F1',
                    borderWidth: 1,
                    borderColor: '#F2C9CD',
                  }}
                >

                  <Text
                    style={{
                      color: '#8B3A42',
                      fontSize: 10,
                      fontWeight: '900',
                      letterSpacing: 1.4,
                    }}
                  >
                    RETURN HERE
                  </Text>

                  <Text
                    style={{
                      marginTop: 5,
                      color: '#E63946',
                      fontSize: 38,
                      fontWeight: '900',
                    }}
                  >
                    {returnReservation.slot}
                  </Text>

                </View>


                <Text style={styles.returnSubtitle}>
                  Put {returnReservation.bike_id} into the physical dock with this exact number. Later the smart dock will confirm the lock automatically.
                </Text>


                <Pressable
                  disabled={endingRide}
                  onPress={confirmDocked}
                  style={[
                    styles.confirmReturnButton,
                    endingRide && styles.disabledButton,
                  ]}
                >

                  {endingRide ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons
                        name="lock-closed-outline"
                        size={20}
                        color="#FFFFFF"
                      />

                      <Text style={styles.confirmReturnText}>
                        I've docked the bike
                      </Text>
                    </>
                  )}

                </Pressable>


                <Pressable
                  disabled={endingRide}
                  onPress={cancelReturnReservation}
                  style={styles.retryButton}
                >

                  <Text style={styles.retryText}>
                    Cancel return assignment
                  </Text>

                </Pressable>


                <Text
                  style={{
                    marginTop: 12,
                    color: '#99948D',
                    fontSize: 9,
                    lineHeight: 14,
                  }}
                >
                  Prototype mode: this confirmation button stands in for the future physical smart-dock lock sensor.
                </Text>

              </View>

            ) : !showStations ? (
'''


BUTTON_ONPRESS_OLD = '''                    onPress={endRide}
'''

BUTTON_ONPRESS_NEW = '''                    onPress={reserveReturnDock}
'''


BUTTON_TEXT_OLD = '''                          Return at {selectedStation.station_name}
'''

BUTTON_TEXT_NEW = '''                          Get dock at {selectedStation.station_name}
'''


NOTE_OLD = '''                CampusBike automatically assigns the first available dock slot at the station you select.
'''

NOTE_NEW = '''                After GPS confirms you are near the station, CampusBike reserves an exact numbered dock for your bike.
'''


def main():
    if not API_PATH.exists() or not RIDE_PATH.exists():
        fail("Run this script from the CampusBike repository after git pull.")

    api_original = API_PATH.read_text(encoding="utf-8")
    ride_original = RIDE_PATH.read_text(encoding="utf-8")

    if (
        "def reserve_return_slot():" in api_original
        or "returnReservation" in ride_original
    ):
        fail(
            "Student return-dock assignment appears to be partially or fully installed already. "
            "Stop so we can inspect before applying anything twice."
        )

    api_text = api_original
    ride_text = ride_original

    api_text = replace_once(
        api_text,
        ACTIVE_RIDE_OLD,
        ACTIVE_RIDE_NEW,
        "active-ride response block",
    )

    api_text = replace_once(
        api_text,
        END_RIDE_MARKER,
        RETURN_ROUTES + END_RIDE_MARKER,
        "end-ride marker",
    )

    api_text = replace_once(
        api_text,
        END_REQUEST_OLD,
        END_REQUEST_NEW,
        "end-ride station request",
    )

    api_text = replace_once(
        api_text,
        SLOT_SELECTION_OLD,
        SLOT_SELECTION_NEW,
        "end-ride slot selection",
    )

    api_text = replace_once(
        api_text,
        OCCUPY_OLD,
        OCCUPY_NEW,
        "end-ride dock occupation",
    )

    ride_text = replace_once(
        ride_text,
        ACTIVE_RIDE_TYPE_OLD,
        ACTIVE_RIDE_TYPE_NEW,
        "ActiveRide type",
    )

    ride_text = replace_once(
        ride_text,
        STATE_OLD,
        STATE_NEW,
        "return reservation state",
    )

    ride_text = replace_once(
        ride_text,
        LOAD_RIDE_OLD,
        LOAD_RIDE_NEW,
        "active ride load state",
    )

    ride_text = replace_once(
        ride_text,
        END_FUNCTION_OLD,
        END_FUNCTION_NEW,
        "endRide function name",
    )

    ride_text = replace_once(
        ride_text,
        DIRECT_COMPLETE_OLD,
        DIRECT_COMPLETE_NEW,
        "direct end-ride API call",
    )

    ride_text = replace_once(
        ride_text,
        NEW_FUNCTIONS_MARKER,
        NEW_FUNCTIONS + NEW_FUNCTIONS_MARKER,
        "loading marker",
    )

    ride_text = replace_once(
        ride_text,
        RETURN_TERNARY_OLD,
        RETURN_TERNARY_NEW,
        "return UI ternary",
    )

    ride_text = replace_once(
        ride_text,
        BUTTON_ONPRESS_OLD,
        BUTTON_ONPRESS_NEW,
        "return button handler",
    )

    ride_text = replace_once(
        ride_text,
        BUTTON_TEXT_OLD,
        BUTTON_TEXT_NEW,
        "return button text",
    )

    ride_text = replace_once(
        ride_text,
        NOTE_OLD,
        NOTE_NEW,
        "return helper note",
    )

    API_PATH.write_text(api_text, encoding="utf-8")
    RIDE_PATH.write_text(ride_text, encoding="utf-8")

    try:
        run("python3", "-m", "py_compile", "campusbike_v2/mobile_api.py")
        run("git", "diff", "--check")

        # Use the project's existing lint/type tooling for the mobile file.
        # Expo's default package includes eslint in this project.
        run(
            "npx",
            "eslint",
            "app/(tabs)/ride.tsx",
        )

    except Exception:
        API_PATH.write_text(api_original, encoding="utf-8")
        RIDE_PATH.write_text(ride_original, encoding="utf-8")
        print("Validation failed; original application files were restored.")
        raise

    print("\nPatch validated. Committing the backend + My Ride changes...")

    run(
        "git",
        "add",
        "campusbike_v2/mobile_api.py",
        "CampusBikeMobile/app/(tabs)/ride.tsx",
    )

    run(
        "git",
        "commit",
        "--only",
        "campusbike_v2/mobile_api.py",
        "CampusBikeMobile/app/(tabs)/ride.tsx",
        "-m",
        "Assign exact docks for student returns",
    )

    # Keep GitHub CLI as Git's HTTPS credential helper in Codespaces.
    try:
        run("gh", "auth", "setup-git")
    except Exception:
        print("gh auth setup-git failed; continuing to git push anyway.")

    run("git", "push", "origin", "main")

    print("\nSUCCESS: Student return dock assignment is installed and pushed.")
    print("Flow: GPS check -> reserve exact dock -> show dock number -> confirm docked -> end ride.")


if __name__ == "__main__":
    main()
