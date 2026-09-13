import { useCallback, useState } from 'react';

import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  ScrollView,
  Alert,
} from 'react-native';

import { Ionicons } from '@expo/vector-icons';

import {
  router,
  useFocusEffect,
} from 'expo-router';

import AsyncStorage from '@react-native-async-storage/async-storage';

import * as Location from 'expo-location';

import { API_BASE_URL, apiFetch } from '../../services/api';


type Student = {
  student_id: string;
  name: string;
  email: string | null;
};


type ActiveRide = {
  ride_id: number;
  bike_id: string;
  student_id: string;
  rented_at: string | null;
  start_station: string | null;
  start_slot: string | null;
  rent_method: string | null;
  qr_verified: number;
  bike_status: string | null;
  lock_status: string | null;
  current_user: string | null;

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
  station_id: number;
  station_name: string;

  display_name?: string | null;
  sponsor_name?: string | null;

  total_slots: number;
  available_slots: number;
  available_bikes: number;

  latitude: number | null;
  longitude: number | null;
};


// =========================================================
// GPS / GEOFENCE
// =========================================================

const RETURN_RADIUS_METERS = 100;

// Phone GPS is not perfectly accurate.
// We allow only a limited accuracy buffer.
const MAX_GPS_BUFFER_METERS = 60;

// If Android reports accuracy worse than this,
// we do not trust the return check.
const MAX_ACCEPTABLE_ACCURACY_METERS = 100;

const GPS_SAMPLE_COUNT = 3;


function degreesToRadians(
  degrees: number
) {

  return degrees * Math.PI / 180;

}


function distanceBetweenMeters(
  latitude1: number,
  longitude1: number,
  latitude2: number,
  longitude2: number
) {

  const earthRadius =
    6371000;


  const latitudeDifference =
    degreesToRadians(
      latitude2 - latitude1
    );


  const longitudeDifference =
    degreesToRadians(
      longitude2 - longitude1
    );


  const firstLatitude =
    degreesToRadians(
      latitude1
    );


  const secondLatitude =
    degreesToRadians(
      latitude2
    );


  const a =
    Math.sin(
      latitudeDifference / 2
    ) ** 2
    +
    Math.cos(
      firstLatitude
    )
    *
    Math.cos(
      secondLatitude
    )
    *
    Math.sin(
      longitudeDifference / 2
    ) ** 2;


  const c =
    2 * Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a)
    );


  return earthRadius * c;

}


export default function RideScreen() {

  const [student, setStudent] =
    useState<Student | null>(null);

  const [ride, setRide] =
    useState<ActiveRide | null>(null);

  const [stations, setStations] =
    useState<Station[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [endingRide, setEndingRide] =
    useState(false);

  const [showStations, setShowStations] =
    useState(false);

  const [selectedStation, setSelectedStation] =
    useState<Station | null>(null);

  const [returnReservation, setReturnReservation] =
    useState<ReturnReservation | null>(null);

  const [error, setError] =
    useState('');


  // Reload whenever user opens My Ride
  useFocusEffect(

    useCallback(() => {

      loadRide();

    }, [])

  );


  // =====================================================
  // LOAD ACTIVE RIDE + STATIONS
  // =====================================================

  async function loadRide() {

    setLoading(true);
    setError('');


    try {

      const saved =
        await AsyncStorage.getItem(
          'campusbike_student'
        );


      if (!saved) {

        router.replace('/');

        return;

      }


      const studentData: Student =
        JSON.parse(saved);


      setStudent(studentData);


      const [
        rideResponse,
        stationResponse,
      ] = await Promise.all([

        apiFetch(
          `${API_BASE_URL}/api/students/${studentData.student_id}/active-ride`
        ),

        apiFetch(
          `${API_BASE_URL}/api/stations`
        ),

      ]);


      const rideData =
        await rideResponse.json();


      const stationData =
        await stationResponse.json();


      if (
        !rideResponse.ok ||
        !rideData.success
      ) {

        throw new Error(
          rideData.message ||
          'Unable to load ride.'
        );

      }


      const activeRide: ActiveRide | null =
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

        setStations(
          stationData
        );

      }


    } catch (error: any) {

      console.log(
        'My Ride error:',
        error
      );


      setError(
        error?.message ||
        'Could not connect to CampusBike.'
      );


    } finally {

      setLoading(false);

    }

  }


  // =====================================================
  // END RIDE
  // =====================================================

  async function reserveReturnDock() {

    if (
      !student ||
      !selectedStation
    ) {

      return;

    }


    setEndingRide(true);


    try {

      // =================================================
      // VERIFY STUDENT IS NEAR RETURN STATION
      // =================================================

      if (
        selectedStation.latitude === null ||
        selectedStation.longitude === null
      ) {

        Alert.alert(
          'Station GPS unavailable',
          `${selectedStation.station_name} does not have GPS coordinates configured yet.`
        );

        return;

      }


      const servicesEnabled =
        await Location.hasServicesEnabledAsync();


      if (!servicesEnabled) {

        Alert.alert(
          'Turn on location',
          'Enable your phone location services before returning the bike.'
        );

        return;

      }


      const {
        status,
      } =
        await Location.requestForegroundPermissionsAsync();


      if (status !== 'granted') {

        Alert.alert(
          'Location permission required',
          'CampusBike needs your location to confirm that you are near the return station.'
        );

        return;

      }


      // =================================================
      // TAKE MULTIPLE GPS SAMPLES
      // =================================================

      const gpsSamples: {
        distance: number;
        accuracy: number;
      }[] = [];


      for (
        let sampleNumber = 0;
        sampleNumber < GPS_SAMPLE_COUNT;
        sampleNumber++
      ) {

        const currentLocation =
          await Location.getCurrentPositionAsync({
            accuracy:
              Location.Accuracy.High,
          });


        const reportedAccuracy =
          typeof currentLocation.coords.accuracy === 'number'

            ? currentLocation.coords.accuracy

            : 9999;


        const sampleDistance =
          distanceBetweenMeters(

            currentLocation.coords.latitude,

            currentLocation.coords.longitude,

            selectedStation.latitude,

            selectedStation.longitude

          );


        gpsSamples.push({
          distance:
            sampleDistance,

          accuracy:
            reportedAccuracy,
        });


        // Give the phone a moment to obtain
        // another GPS fix instead of immediately
        // asking for the same cached position.
        if (
          sampleNumber <
          GPS_SAMPLE_COUNT - 1
        ) {

          await new Promise(
            resolve =>
              setTimeout(
                resolve,
                700
              )
          );

        }

      }


      // =================================================
      // REJECT VERY WEAK GPS
      // =================================================

      const usableSamples =
        gpsSamples.filter(
          sample =>
            sample.accuracy <=
            MAX_ACCEPTABLE_ACCURACY_METERS
        );


      if (
        usableSamples.length === 0
      ) {

        Alert.alert(
          'GPS signal is weak',
          'CampusBike cannot confirm your return location accurately. Move to an open area near the station and try again.'
        );

        return;

      }


      // =================================================
      // USE MEDIAN DISTANCE
      //
      // Example:
      // 22 m, 28 m, 178 m
      //
      // Result = 28 m
      //
      // One bad GPS jump will not incorrectly
      // reject the rider.
      // =================================================

      const sortedDistances =
        usableSamples
          .map(
            sample =>
              sample.distance
          )
          .sort(
            (a, b) =>
              a - b
          );


      const middleIndex =
        Math.floor(
          sortedDistances.length / 2
        );


      const distance =
        sortedDistances[
          middleIndex
        ];


      // Best reported accuracy from the samples.
      const bestAccuracy =
        Math.min(
          ...usableSamples.map(
            sample =>
              sample.accuracy
          )
        );


      // Never allow GPS uncertainty to make the
      // geofence excessively large.
      const gpsBuffer =
        Math.min(
          bestAccuracy,
          MAX_GPS_BUFFER_METERS
        );


      const allowedDistance =
        RETURN_RADIUS_METERS +
        gpsBuffer;


      // =================================================
      // CHECK RETURN DISTANCE
      // =================================================

      if (
        distance >
        allowedDistance
      ) {

        const readableDistance =
          distance >= 1000

            ? `${(
                distance / 1000
              ).toFixed(1)} km`

            : `${Math.round(
                distance
              )} m`;


        Alert.alert(
          'Too far from station',
          `CampusBike estimates you are about ${readableDistance} from ${selectedStation.station_name}. GPS accuracy is about ±${Math.round(bestAccuracy)} m. Move closer to the station and try again.`
        );

        return;

      }


      // =================================================
      // GPS CHECK PASSED — RESERVE AN EXACT RETURN DOCK
      // =================================================

      const response = await apiFetch(
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


    } catch (error) {

      console.log(
        'End ride error:',
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

      const response = await apiFetch(
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

      const response = await apiFetch(
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


  // =====================================================
  // LOADING
  // =====================================================

  if (loading) {

    return (

      <SafeAreaView style={styles.page}>

        <View style={styles.center}>

          <ActivityIndicator
            color="#E63946"
          />

          <Text style={styles.loadingText}>
            Checking your ride...
          </Text>

        </View>

      </SafeAreaView>

    );

  }


  // =====================================================
  // SCREEN
  // =====================================================

  return (

    <SafeAreaView style={styles.page}>

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >


        {/* HEADER */}

        <Text style={styles.brand}>
          CAMPUSBIKE
        </Text>


        <Text style={styles.title}>
          My Ride
        </Text>


        <Text style={styles.subtitle}>

          {student?.name
            ? `${student.name}'s ride`
            : 'Your current ride'}

        </Text>



        {/* ERROR */}

        {error ? (

          <View style={styles.errorCard}>

            <Ionicons
              name="cloud-offline-outline"
              size={27}
              color="#E63946"
            />


            <Text style={styles.errorTitle}>
              Couldn&apos;t load your ride
            </Text>


            <Text style={styles.errorText}>
              {error}
            </Text>


            <Pressable
              style={styles.retryButton}
              onPress={loadRide}
            >

              <Text style={styles.retryText}>
                Try again
              </Text>

            </Pressable>

          </View>


        ) : ride ? (

          <>


            {/* ACTIVE RIDE CARD */}

            <View style={styles.activeCard}>


              <View style={styles.activeTop}>


                <View>

                  <Text style={styles.smallLabel}>
                    CURRENT BIKE
                  </Text>


                  <Text style={styles.bikeId}>
                    {ride.bike_id}
                  </Text>

                </View>



                <View style={styles.activeBadge}>

                  <View style={styles.activeDot} />

                  <Text style={styles.activeBadgeText}>
                    ACTIVE
                  </Text>

                </View>


              </View>



              <View style={styles.bikeGraphic}>

                <Ionicons
                  name="bicycle"
                  size={78}
                  color="#E63946"
                />

              </View>



              <View style={styles.infoGrid}>


                <View style={styles.infoBlock}>

                  <Text style={styles.infoLabel}>
                    START STATION
                  </Text>

                  <Text style={styles.infoValue}>
                    {ride.start_station || '—'}
                  </Text>

                </View>


                <View style={styles.infoBlock}>

                  <Text style={styles.infoLabel}>
                    START SLOT
                  </Text>

                  <Text style={styles.infoValue}>
                    {ride.start_slot || '—'}
                  </Text>

                </View>


                <View style={styles.infoBlock}>

                  <Text style={styles.infoLabel}>
                    BIKE STATUS
                  </Text>

                  <Text style={styles.infoValue}>
                    {ride.bike_status || 'In use'}
                  </Text>

                </View>


                <View style={styles.infoBlock}>

                  <Text style={styles.infoLabel}>
                    RIDE ID
                  </Text>

                  <Text style={styles.infoValue}>
                    #{ride.ride_id}
                  </Text>

                </View>


              </View>


            </View>



            {/* END RIDE */}

            {returnReservation ? (

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
                        I&apos;ve docked the bike
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

              <Pressable
                style={styles.endRideButton}
                onPress={() =>
                  setShowStations(true)
                }
              >

                <Ionicons
                  name="lock-closed-outline"
                  size={20}
                  color="#FFFFFF"
                />


                <Text style={styles.endRideButtonText}>
                  End Ride
                </Text>

              </Pressable>

            ) : (

              <View style={styles.returnCard}>


                <View style={styles.returnHeader}>

                  <View>

                    <Text style={styles.returnTitle}>
                      Return bike
                    </Text>

                    <Text style={styles.returnSubtitle}>
                      Choose a station with an open slot.
                    </Text>

                  </View>


                  <Pressable
                    onPress={() => {

                      setShowStations(false);

                      setSelectedStation(null);

                    }}
                  >

                    <Ionicons
                      name="close"
                      size={23}
                      color="#77736D"
                    />

                  </Pressable>

                </View>



                {/* RETURN STATIONS */}

                {stations.map((station) => {

                  const available =
                    station.available_slots > 0;


                  const selected =
                    selectedStation?.station_id ===
                    station.station_id;


                  return (

                    <Pressable

                      key={station.station_id}

                      disabled={!available}

                      onPress={() =>
                        setSelectedStation(station)
                      }

                      style={[
                        styles.returnStation,

                        selected &&
                        styles.returnStationSelected,

                        !available &&
                        styles.returnStationDisabled,
                      ]}

                    >


                      <View style={styles.returnStationIcon}>

                        <Ionicons
                          name="location-outline"
                          size={20}
                          color={
                            selected
                              ? '#FFFFFF'
                              : '#E63946'
                          }
                        />

                      </View>



                      <View style={styles.returnStationInfo}>

                        <Text
                          style={[
                            styles.returnStationName,

                            selected &&
                            styles.returnStationNameSelected,
                          ]}
                        >
                          {station.station_name}
                        </Text>


                        <Text
                          style={[
                            styles.returnStationSlots,

                            selected &&
                            styles.returnStationSlotsSelected,
                          ]}
                        >

                          {available
                            ? `${station.available_slots} open slots`
                            : 'Station full'}

                        </Text>

                      </View>



                      {selected ? (

                        <Ionicons
                          name="checkmark-circle"
                          size={22}
                          color="#FFFFFF"
                        />

                      ) : (

                        <Ionicons
                          name="chevron-forward"
                          size={18}
                          color="#AAA59D"
                        />

                      )}


                    </Pressable>

                  );

                })}



                {/* CONFIRM RETURN */}

                {selectedStation ? (

                  <Pressable

                    disabled={endingRide}

                    onPress={reserveReturnDock}

                    style={[
                      styles.confirmReturnButton,

                      endingRide &&
                      styles.disabledButton,
                    ]}

                  >

                    {endingRide ? (

                      <ActivityIndicator
                        color="#FFFFFF"
                      />

                    ) : (

                      <>

                        <Ionicons
                          name="checkmark-circle-outline"
                          size={20}
                          color="#FFFFFF"
                        />

                        <Text style={styles.confirmReturnText}>
                          Get dock at {selectedStation.station_name}
                        </Text>

                      </>

                    )}

                  </Pressable>

                ) : null}


              </View>

            )}



            <View style={styles.returnNote}>

              <Ionicons
                name="information-circle-outline"
                size={19}
                color="#77736D"
              />


              <Text style={styles.returnNoteText}>
                After GPS confirms you are near the station, CampusBike reserves an exact numbered dock for your bike.
              </Text>

            </View>


          </>


        ) : (

          <>


            {/* NO ACTIVE RIDE */}

            <View style={styles.emptyCard}>


              <View style={styles.emptyIcon}>

                <Ionicons
                  name="bicycle-outline"
                  size={48}
                  color="#E63946"
                />

              </View>


              <Text style={styles.emptyTitle}>
                No active ride
              </Text>


              <Text style={styles.emptyText}>
                You don&apos;t currently have a CampusBike checked out.
              </Text>


              <Pressable
                style={styles.findButton}
                onPress={() =>
                  router.push('/(tabs)')
                }
              >

                <Ionicons
                  name="location-outline"
                  size={19}
                  color="#FFFFFF"
                />


                <Text style={styles.findButtonText}>
                  Find a bike
                </Text>

              </Pressable>


            </View>


          </>

        )}



        <View style={styles.bottomSpace} />


      </ScrollView>

    </SafeAreaView>

  );

}


// =========================================================
// STYLES
// =========================================================

const styles = StyleSheet.create({

  page: {
    flex: 1,
    backgroundColor: '#F7F5F0',
  },


  content: {
    paddingHorizontal: 20,
    paddingTop: 25,
  },


  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },


  loadingText: {
    marginTop: 10,
    color: '#77736D',
    fontSize: 12,
  },


  brand: {
    color: '#E63946',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 2.3,
  },


  title: {
    marginTop: 6,
    color: '#151515',
    fontSize: 31,
    fontWeight: '800',
    letterSpacing: -0.8,
  },


  subtitle: {
    marginTop: 5,
    color: '#77736D',
    fontSize: 12,
    marginBottom: 25,
  },


  // ACTIVE RIDE

  activeCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    borderWidth: 1,
    borderColor: '#E2DED7',
    padding: 20,
  },


  activeTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },


  smallLabel: {
    color: '#99948D',
    fontSize: 8,
    fontWeight: '900',
    letterSpacing: 1.2,
  },


  bikeId: {
    marginTop: 4,
    color: '#151515',
    fontSize: 26,
    fontWeight: '900',
  },


  activeBadge: {
    backgroundColor: '#EDF7F0',
    borderRadius: 9,
    paddingHorizontal: 9,
    paddingVertical: 6,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },


  activeDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#257C45',
  },


  activeBadgeText: {
    color: '#257C45',
    fontSize: 8,
    fontWeight: '900',
  },


  bikeGraphic: {
    height: 130,
    alignItems: 'center',
    justifyContent: 'center',
  },


  infoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    borderTopWidth: 1,
    borderTopColor: '#EFECE7',
    paddingTop: 13,
  },


  infoBlock: {
    width: '50%',
    paddingVertical: 10,
  },


  infoLabel: {
    color: '#99948D',
    fontSize: 8,
    fontWeight: '900',
    letterSpacing: 1,
  },


  infoValue: {
    marginTop: 4,
    color: '#151515',
    fontSize: 13,
    fontWeight: '700',
  },


  // END RIDE BUTTON

  endRideButton: {
    height: 55,
    marginTop: 18,
    borderRadius: 15,
    backgroundColor: '#151515',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
  },


  endRideButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },


  // RETURN PANEL

  returnCard: {
    marginTop: 18,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#E2DED7',
    padding: 16,
  },


  returnHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 15,
  },


  returnTitle: {
    color: '#151515',
    fontSize: 18,
    fontWeight: '800',
  },


  returnSubtitle: {
    color: '#77736D',
    fontSize: 10,
    marginTop: 3,
  },


  returnStation: {
    minHeight: 65,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#E5E1DA',
    marginBottom: 9,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },


  returnStationSelected: {
    backgroundColor: '#E63946',
    borderColor: '#E63946',
  },


  returnStationDisabled: {
    opacity: 0.4,
  },


  returnStationIcon: {
    width: 38,
    alignItems: 'center',
  },


  returnStationInfo: {
    flex: 1,
    marginLeft: 7,
  },


  returnStationName: {
    color: '#151515',
    fontSize: 13,
    fontWeight: '800',
  },


  returnStationNameSelected: {
    color: '#FFFFFF',
  },


  returnStationSlots: {
    marginTop: 3,
    color: '#77736D',
    fontSize: 10,
  },


  returnStationSlotsSelected: {
    color: '#FFE8EA',
  },


  confirmReturnButton: {
    height: 53,
    marginTop: 8,
    backgroundColor: '#E63946',
    borderRadius: 14,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },


  confirmReturnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },


  disabledButton: {
    opacity: 0.6,
  },


  returnNote: {
    marginTop: 14,
    padding: 14,
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2DED7',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
  },


  returnNoteText: {
    flex: 1,
    color: '#77736D',
    fontSize: 10,
    lineHeight: 16,
  },


  // EMPTY

  emptyCard: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2DED7',
    borderRadius: 22,
    padding: 25,
    alignItems: 'center',
  },


  emptyIcon: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: '#FFF0F1',
    alignItems: 'center',
    justifyContent: 'center',
  },


  emptyTitle: {
    marginTop: 20,
    color: '#151515',
    fontSize: 21,
    fontWeight: '800',
  },


  emptyText: {
    marginTop: 7,
    color: '#77736D',
    fontSize: 12,
    lineHeight: 18,
    textAlign: 'center',
  },


  findButton: {
    marginTop: 22,
    height: 51,
    paddingHorizontal: 25,
    borderRadius: 14,
    backgroundColor: '#E63946',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },


  findButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },


  // ERROR

  errorCard: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E8C9CC',
    borderRadius: 20,
    padding: 25,
    alignItems: 'center',
  },


  errorTitle: {
    marginTop: 12,
    color: '#151515',
    fontSize: 18,
    fontWeight: '800',
  },


  errorText: {
    marginTop: 6,
    color: '#77736D',
    fontSize: 12,
    textAlign: 'center',
  },


  retryButton: {
    marginTop: 18,
    borderRadius: 12,
    backgroundColor: '#E63946',
    paddingHorizontal: 20,
    paddingVertical: 11,
  },


  retryText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 12,
  },


  bottomSpace: {
    height: 40,
  },

});