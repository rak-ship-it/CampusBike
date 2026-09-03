import {
  useCallback,
  useEffect,
  useState,
} from 'react';

import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import {
  router,
  useFocusEffect,
} from 'expo-router';

import { Ionicons } from '@expo/vector-icons';

import AsyncStorage from
  '@react-native-async-storage/async-storage';

import * as Location from 'expo-location';

import MapView, {
  Marker,
  Polygon,
  Region,
} from 'react-native-maps';

import { SafeAreaView } from
  'react-native-safe-area-context';

import {
  API_BASE_URL,
} from '../../services/api';


// =========================================================
// TYPES
// =========================================================

type Student = {
  student_id: string;
  name: string;
  email?: string | null;
};


type Bike = {
  bike_id: string;
  status?: string;
  slot?: string | null;
  station?: string | null;
};


type CampusBoundaryPoint = {
  latitude: number;
  longitude: number;
};


type Station = {
  station_id: number;
  station_name: string;

  display_name?: string | null;
  sponsor_name?: string | null;
  station_code?: string | null;

  total_slots?: number;

  available_bikes: number;
  available_slots: number;

  latitude: number | null;
  longitude: number | null;

  bikes: Bike[];
};


// =========================================================
// CAMPUS GEOFENCE
// =========================================================

type GeofenceStatus =
  | 'checking'
  | 'inside'
  | 'outside'
  | 'unavailable';


function isPointInsidePolygon(
  point: CampusBoundaryPoint,
  polygon: CampusBoundaryPoint[]
) {

  if (
    polygon.length < 3
  ) {

    return false;

  }


  let inside = false;


  const x =
    point.longitude;

  const y =
    point.latitude;


  for (
    let i = 0,
        j = polygon.length - 1;

    i < polygon.length;

    j = i++
  ) {

    const xi =
      polygon[i].longitude;

    const yi =
      polygon[i].latitude;

    const xj =
      polygon[j].longitude;

    const yj =
      polygon[j].latitude;


    const crosses =
      (
        (yi > y) !==
        (yj > y)
      )
      &&
      (
        x <
        (
          (xj - xi)
          *
          (y - yi)
          /
          (
            (yj - yi)
            || 0.0000000001
          )
          +
          xi
        )
      );


    if (crosses) {

      inside =
        !inside;

    }

  }


  return inside;

}


// =========================================================
// SCREEN
// =========================================================

export default function MapScreen() {

  // =====================================================
  // STATE
  // =====================================================

  const [
    student,
    setStudent,
  ] = useState<Student | null>(
    null
  );


  const [
    stations,
    setStations,
  ] = useState<Station[]>(
    []
  );


  const [
    campusBoundary,
    setCampusBoundary,
  ] = useState<CampusBoundaryPoint[]>(
    []
  );


  const [
    region,
    setRegion,
  ] = useState<Region | null>(
    null
  );


  const [
    locationAllowed,
    setLocationAllowed,
  ] = useState(true);


  const [
    backendConnected,
    setBackendConnected,
  ] = useState(false);


  const [
    loadingStations,
    setLoadingStations,
  ] = useState(true);


  const [
    refreshing,
    setRefreshing,
  ] = useState(false);


  const [
    selectedStation,
    setSelectedStation,
  ] = useState<Station | null>(
    null
  );


  const [
    geofenceStatus,
    setGeofenceStatus,
  ] = useState<GeofenceStatus>(
    'checking'
  );


  const [
    geofenceAccuracy,
    setGeofenceAccuracy,
  ] = useState<number | null>(
    null
  );


  // =====================================================
  // LOGGED IN STUDENT
  // =====================================================

  const loadStudent = useCallback(
    async () => {

      try {

        const savedStudent =
          await AsyncStorage.getItem(
            'campusbike_student'
          );


        if (!savedStudent) {

          router.replace('/');

          return;

        }


        const parsedStudent:
          Student =
          JSON.parse(
            savedStudent
          );


        setStudent(
          parsedStudent
        );

      } catch (error) {

        console.log(
          'Student load error:',
          error
        );

      }

    },
    []
  );


  // =====================================================
  // LOCATION
  // =====================================================

  const loadLocation = useCallback(
    async () => {

      try {

        const servicesEnabled =
          await Location
            .hasServicesEnabledAsync();


        if (!servicesEnabled) {

          setLocationAllowed(
            false
          );

          return;

        }


        const permission =
          await Location
            .requestForegroundPermissionsAsync();


        if (
          permission.status !==
          'granted'
        ) {

          setLocationAllowed(
            false
          );

          return;

        }


        setLocationAllowed(
          true
        );


        // ---------------------------------------------
        // Try last-known GPS first.
        // Faster than waiting for a fresh GPS fix.
        // ---------------------------------------------

        let location =
          await Location
            .getLastKnownPositionAsync();


        // ---------------------------------------------
        // If no previous GPS position exists,
        // request a fresh balanced-accuracy location.
        // ---------------------------------------------

        if (!location) {

          location =
            await Location
              .getCurrentPositionAsync({

                accuracy:
                  Location.Accuracy
                    .Balanced,

              });

        }


        setRegion({

          latitude:
            location.coords.latitude,

          longitude:
            location.coords.longitude,

          latitudeDelta:
            0.008,

          longitudeDelta:
            0.008,

        });

      } catch (error) {

        console.log(
          'Location error:',
          error
        );


        setLocationAllowed(
          false
        );

      }

    },
    []
  );


  // =====================================================
  // LIVE STATIONS
  // =====================================================

  const loadStations =
    useCallback(
      async () => {

        try {

          /*
           * Timestamp prevents an intermediate
           * browser/proxy cache from returning
           * old station information.
           */

          const response =
            await fetch(
              `${API_BASE_URL}/api/stations?t=${Date.now()}`
            );


          if (!response.ok) {

            throw new Error(
              `Station API returned ${response.status}`
            );

          }


          const payload =
            await response.json();


          /*
           * Supports both:
           *
           * [
           *   {...station}
           * ]
           *
           * and:
           *
           * {
           *   stations: [...]
           * }
           *
           * so the mobile app stays safe if the API
           * wrapper changes later.
           */

          const rawStations =
            Array.isArray(payload)

              ? payload

              : Array.isArray(
                  payload?.stations
                )

                ? payload.stations

                : [];


          const data: Station[] =
            rawStations.map(
              (station: any) => ({

                ...station,

                station_id:
                  Number(
                    station.station_id
                  ),

                available_bikes:
                  Number(
                    station.available_bikes
                    ?? 0
                  ),

                available_slots:
                  Number(
                    station.available_slots
                    ?? 0
                  ),

                total_slots:
                  Number(
                    station.total_slots
                    ?? 0
                  ),

                latitude:
                  station.latitude ===
                    null ||
                  station.latitude ===
                    undefined

                    ? null

                    : Number(
                        station.latitude
                      ),

                longitude:
                  station.longitude ===
                    null ||
                  station.longitude ===
                    undefined

                    ? null

                    : Number(
                        station.longitude
                      ),

                bikes:
                  Array.isArray(
                    station.bikes
                  )

                    ? station.bikes

                    : [],

              })
            );


          setStations(
            data
          );


          setBackendConnected(
            true
          );

        } catch (error) {

          console.log(
            'Station API error:',
            error
          );


          setBackendConnected(
            false
          );

        } finally {

          setLoadingStations(
            false
          );

        }

      },
      []
    );


  // =====================================================
  // CAMPUS SERVICE AREA
  // =====================================================

  const loadCampusBoundary =
    useCallback(
      async () => {

        try {

          const response =
            await fetch(
              `${API_BASE_URL}/api/campus-boundary?t=${Date.now()}`
            );


          if (!response.ok) {

            throw new Error(
              `Campus boundary API returned ${response.status}`
            );

          }


          const payload =
            await response.json();


          const rawPoints =
            Array.isArray(
              payload?.points
            )

              ? payload.points

              : [];


          const points:
            CampusBoundaryPoint[] =
            rawPoints
              .map(
                (point: any) => ({

                  latitude:
                    Number(
                      point.latitude
                    ),

                  longitude:
                    Number(
                      point.longitude
                    ),

                })
              )
              .filter(
                (
                  point:
                    CampusBoundaryPoint
                ) =>
                  Number.isFinite(
                    point.latitude
                  )
                  &&
                  Number.isFinite(
                    point.longitude
                  )
              );


          setCampusBoundary(
            points
          );


        } catch (error) {

          console.log(
            'Campus boundary API error:',
            error
          );

        }

      },
      []
    );


  // =====================================================
  // GPS — LOAD ONCE
  // =====================================================

  useEffect(
    () => {

      loadLocation();

    },
    [
      loadLocation,
    ]
  );


  // =====================================================
  // LIVE AUTO REFRESH
  // =====================================================
  //
  // This is the important new part.
  //
  // When Map becomes active:
  //     refresh immediately
  //
  // While student stays on Map:
  //     refresh every 5 seconds
  //
  // When student leaves Map:
  //     stop the timer
  //
  // So students NEVER need to manually reload.
  // =====================================================

  useFocusEffect(

    useCallback(
      () => {

        loadStudent();

        loadStations();

        loadCampusBoundary();


        const refreshTimer =
          setInterval(
            () => {

              loadStations();

            },
            5000
          );


        return () => {

          clearInterval(
            refreshTimer
          );

        };

      },
      [
        loadStudent,
        loadStations,
        loadCampusBoundary,
      ]
    )

  );


  // =====================================================
  // LIVE CAMPUS GEOFENCE
  // =====================================================
  //
  // This is intentionally a WARNING system.
  //
  // It does not lock a bike or end a ride.
  //
  // Poor GPS readings are ignored and a rider must be
  // outside for 3 consecutive usable readings before
  // the app changes to "Outside service area".
  // =====================================================

  useFocusEffect(

    useCallback(
      () => {

        if (
          campusBoundary.length < 3
        ) {

          setGeofenceStatus(
            'unavailable'
          );

          return;

        }


        let subscription:
          Location.LocationSubscription
          | null =
          null;


        let cancelled =
          false;


        let consecutiveOutside =
          0;


        async function startGeofenceWatch() {

          try {

            const servicesEnabled =
              await Location
                .hasServicesEnabledAsync();


            if (
              !servicesEnabled
            ) {

              if (!cancelled) {

                setGeofenceStatus(
                  'unavailable'
                );

              }

              return;

            }


            const permission =
              await Location
                .getForegroundPermissionsAsync();


            if (
              permission.status !==
              'granted'
            ) {

              if (!cancelled) {

                setGeofenceStatus(
                  'unavailable'
                );

              }

              return;

            }


            if (!cancelled) {

              setGeofenceStatus(
                'checking'
              );

            }


            subscription =
              await Location
                .watchPositionAsync(

                  {

                    accuracy:
                      Location.Accuracy
                        .High,

                    timeInterval:
                      3000,

                    distanceInterval:
                      5,

                  },

                  location => {

                    if (cancelled) {
                      return;
                    }


                    const accuracy =
                      location.coords
                        .accuracy
                      ??
                      9999;


                    setGeofenceAccuracy(
                      accuracy
                    );


                    // ---------------------------------
                    // Do not trust very weak GPS.
                    // ---------------------------------

                    if (
                      accuracy > 100
                    ) {

                      return;

                    }


                    const point = {

                      latitude:
                        location.coords
                          .latitude,

                      longitude:
                        location.coords
                          .longitude,

                    };


                    const inside =
                      isPointInsidePolygon(
                        point,
                        campusBoundary
                      );


                    if (inside) {

                      consecutiveOutside =
                        0;


                      setGeofenceStatus(
                        'inside'
                      );


                      return;

                    }


                    // ---------------------------------
                    // Require 3 outside readings.
                    // Helps prevent one GPS jump from
                    // showing a false warning.
                    // ---------------------------------

                    consecutiveOutside +=
                      1;


                    if (
                      consecutiveOutside >= 3
                    ) {

                      setGeofenceStatus(
                        'outside'
                      );

                    }

                  }

                );


            if (
              cancelled
              &&
              subscription
            ) {

              subscription.remove();

            }

          } catch (error) {

            console.log(
              'Geofence GPS error:',
              error
            );


            if (!cancelled) {

              setGeofenceStatus(
                'unavailable'
              );

            }

          }

        }


        startGeofenceWatch();


        return () => {

          cancelled =
            true;


          if (subscription) {

            subscription.remove();

          }

        };

      },
      [
        campusBoundary,
      ]
    )

  );


  // =====================================================
  // MANUAL PULL TO REFRESH
  // =====================================================

  async function refresh() {

    setRefreshing(
      true
    );


    await Promise.all([

      loadStudent(),

      loadStations(),

      loadCampusBoundary(),

    ]);


    setRefreshing(
      false
    );

  }


  // =====================================================
  // SELECT BIKE -> SCANNER
  // =====================================================

  function rentBike(
    _bikeId: string
  ) {

    // The bike number is intentionally NOT passed.
    // Student scans whichever available bike is
    // physically in front of them.

    router.push(
      '/scanner'
    );

  }


  // =====================================================
  // QUICK SCAN
  // =====================================================

  function quickScan() {

    router.push(
      '/scanner'
    );

  }


  // =====================================================
  // UI
  // =====================================================

  return (

    <SafeAreaView
      style={styles.page}
    >

      <ScrollView

        showsVerticalScrollIndicator={
          false
        }

        contentContainerStyle={
          styles.content
        }

        refreshControl={

          <RefreshControl

            refreshing={
              refreshing
            }

            onRefresh={
              refresh
            }

            tintColor="#E63946"

          />

        }

      >


        {/* =================================================
            HEADER
        ================================================== */}

        <View
          style={styles.header}
        >


          <View
            style={styles.headerText}
          >

            <Text
              style={styles.brand}
            >
              CAMPUSBIKE
            </Text>


            <Text
              style={styles.welcome}
            >
              Hi, {student?.name || 'Student'}
            </Text>


            <Text
              style={styles.heading}
            >
              Find your next ride
            </Text>


            <View
              style={
                styles.connectionRow
              }
            >

              <View

                style={[

                  styles.connectionDot,

                  backendConnected

                    ? styles.connected

                    : styles.connecting,

                ]}

              />


              <Text
                style={
                  styles.connectionText
                }
              >

                {
                  backendConnected

                    ? 'Live network'

                    : 'Connecting...'
                }

              </Text>

            </View>

          </View>



          <Pressable

            style={
              styles.profileButton
            }

            onPress={() =>
              router.push(
                '/profile'
              )
            }

          >

            <Text
              style={
                styles.profileInitial
              }
            >

              {
                student?.name
                  ?.charAt(0)
                  .toUpperCase()
                ||
                'S'
              }

            </Text>

          </Pressable>


        </View>



        {/* =================================================
            MAP
        ================================================== */}

        <View
          style={styles.mapCard}
        >

          {region ? (

            <MapView

              style={styles.map}

              initialRegion={
                region
              }

              showsUserLocation={
                true
              }

              showsMyLocationButton={
                true
              }

            >

              {
                campusBoundary.length >= 3
                &&
                (
                  <Polygon

                    coordinates={
                      campusBoundary
                    }

                    strokeColor="#E63946"

                    fillColor="rgba(230, 57, 70, 0.10)"

                    strokeWidth={3}

                  />
                )
              }


              {
                stations.map(
                  (
                    station
                  ) => {

                    if (
                      station.latitude ===
                        null
                      ||
                      station.longitude ===
                        null
                    ) {

                      return null;

                    }


                    return (

                      <Marker

                        key={
                          station.station_id
                        }

                        coordinate={{

                          latitude:
                            station.latitude,

                          longitude:
                            station.longitude,

                        }}

                        title={
                          station.station_name
                        }

                        description={
                          `${station.available_bikes} bikes · ${station.available_slots} slots`
                        }

                        pinColor="#E63946"

                        onPress={() =>
                          setSelectedStation(
                            station
                          )
                        }

                      />

                    );

                  }
                )
              }

            </MapView>

          ) : locationAllowed ? (

            <View
              style={
                styles.mapLoading
              }
            >

              <ActivityIndicator
                color="#E63946"
              />


              <Text
                style={
                  styles.mapLoadingText
                }
              >
                Finding your location...
              </Text>

            </View>

          ) : (

            <View
              style={
                styles.mapLoading
              }
            >

              <Ionicons

                name="location-outline"

                size={30}

                color="#77736D"

              />


              <Text
                style={
                  styles.mapLoadingTitle
                }
              >
                Location is off
              </Text>


              <Text
                style={
                  styles.mapLoadingText
                }
              >
                Allow location access to use the CampusBike map.
              </Text>


              <Pressable

                style={
                  styles.locationButton
                }

                onPress={
                  loadLocation
                }

              >

                <Text
                  style={
                    styles.locationButtonText
                  }
                >
                  Try again
                </Text>

              </Pressable>

            </View>

          )}

        </View>



        <Text
          style={styles.mapNote}
        >
          Red outline shows the CampusBike service area.
        </Text>


        <View
          style={{
            marginTop: 10,
            marginBottom: 6,
            paddingVertical: 11,
            paddingHorizontal: 13,
            borderRadius: 12,
            borderWidth: 1,

            borderColor:
              geofenceStatus === 'outside'
                ? '#E63946'
                : geofenceStatus === 'inside'
                  ? '#B7D8C2'
                  : '#DDD8D1',

            backgroundColor:
              geofenceStatus === 'outside'
                ? '#FFF1F2'
                : geofenceStatus === 'inside'
                  ? '#F2F8F4'
                  : '#F8F7F5',
          }}
        >

          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 8,
            }}
          >

            <Ionicons

              name={
                geofenceStatus === 'inside'
                  ? 'checkmark-circle-outline'
                  : geofenceStatus === 'outside'
                    ? 'warning-outline'
                    : 'location-outline'
              }

              size={19}

              color={
                geofenceStatus === 'outside'
                  ? '#E63946'
                  : geofenceStatus === 'inside'
                    ? '#3F7D55'
                    : '#77736D'
              }

            />


            <Text
              style={{
                fontSize: 12,
                fontWeight: '900',

                color:
                  geofenceStatus === 'outside'
                    ? '#E63946'
                    : geofenceStatus === 'inside'
                      ? '#315E40'
                      : '#615D58',
              }}
            >

              {
                geofenceStatus === 'inside'
                  ? 'Inside service area'
                  : geofenceStatus === 'outside'
                    ? 'Outside service area'
                    : geofenceStatus === 'unavailable'
                      ? 'Service area location unavailable'
                      : 'Checking service area...'
              }

            </Text>

          </View>


          {
            geofenceStatus === 'outside'
            &&
            (
              <Text
                style={{
                  marginTop: 5,
                  fontSize: 10,
                  lineHeight: 15,
                  color: '#756D68',
                }}
              >
                Please ride back toward the CampusBike service area.
                Your ride will not be stopped automatically.
              </Text>
            )
          }


          {
            geofenceAccuracy !== null
            &&
            (
              <Text
                style={{
                  marginTop: 4,
                  fontSize: 9,
                  color: '#9A958F',
                }}
              >
                GPS accuracy approximately ±{
                  Math.round(
                    geofenceAccuracy
                  )
                } m
              </Text>
            )
          }

        </View>



        {/* =================================================
            RED SCAN BUTTON
        ================================================== */}

        <Pressable

          style={({
            pressed,
          }) => [

            styles.scanButton,

            pressed &&
              styles.scanButtonPressed,

          ]}

          onPress={
            quickScan
          }

        >

          <Ionicons

            name="qr-code-outline"

            size={22}

            color="#FFFFFF"

          />


          <Text
            style={
              styles.scanButtonText
            }
          >
            Scan a bike
          </Text>

        </Pressable>



        {/* =================================================
            STATIONS
        ================================================== */}

        <View
          style={
            styles.sectionHeader
          }
        >

          <Text
            style={
              styles.sectionTitle
            }
          >
            Stations
          </Text>


          <Text
            style={
              styles.sectionMeta
            }
          >
            {stations.length} active
          </Text>

        </View>



        {loadingStations ? (

          <ActivityIndicator

            color="#E63946"

            style={
              styles.stationLoader
            }

          />

        ) : (

          stations.map(
            (
              station
            ) => (

              <View

                key={
                  station.station_id
                }

                style={
                  styles.stationCard
                }

              >


                {/* STATION HEADER */}

                <Pressable

                  style={
                    styles.stationTop
                  }

                  onPress={() =>

                    setSelectedStation(

                      selectedStation
                        ?.station_id ===
                      station.station_id

                        ? null

                        : station

                    )

                  }

                >


                  <View
                    style={
                      styles.stationIcon
                    }
                  >

                    <Ionicons

                      name="location-outline"

                      size={21}

                      color="#E63946"

                    />

                  </View>



                  <View
                    style={
                      styles.stationInfo
                    }
                  >

                    <Text
                      style={
                        styles.stationName
                      }
                    >

                      {station.sponsor_name ? (
                        <>
                          <Text
                            style={{
                              color: '#E63946',
                              fontWeight: '900',
                            }}
                          >
                            {station.sponsor_name.toUpperCase()}
                          </Text>

                          {' '}
                        </>
                      ) : null}

                      {
                        station.display_name ||
                        station.station_name
                      }

                    </Text>


                    <Text
                      style={
                        styles.stationDetails
                      }
                    >

                      {station.available_bikes}{' '}

                      {
                        station.available_bikes ===
                        1

                          ? 'bike'

                          : 'bikes'
                      }

                      {' available · '}

                      {
                        station.available_slots
                      }

                      {' open slots'}

                    </Text>

                  </View>



                  <Ionicons

                    name={

                      selectedStation
                        ?.station_id ===
                      station.station_id

                        ? 'chevron-up'

                        : 'chevron-down'

                    }

                    size={18}

                    color="#9B9790"

                  />

                </Pressable>



                {/* EXPANDED STATION */}

                {
                  selectedStation
                    ?.station_id ===
                  station.station_id
                  && (

                    <View
                      style={
                        styles.stationExpanded
                      }
                    >


                      {
                        station.bikes.length >
                        0
                        ? (

                          station.bikes.map(
                            (
                              bike
                            ) => (

                              <View

                                key={
                                  bike.bike_id
                                }

                                style={
                                  styles.bikeCard
                                }

                              >


                                <View
                                  style={
                                    styles.bikeLeft
                                  }
                                >


                                  <View
                                    style={
                                      styles.bikeIcon
                                    }
                                  >

                                    <Ionicons

                                      name="bicycle"

                                      size={23}

                                      color="#E63946"

                                    />

                                  </View>


                                  <View>

                                    <Text
                                      style={
                                        styles.bikeName
                                      }
                                    >
                                      {bike.bike_id}
                                    </Text>


                                    <Text
                                      style={
                                        styles.bikeSlot
                                      }
                                    >
                                      Docked at {bike.slot || 'station'}
                                    </Text>


                                    <View
                                      style={
                                        styles.availableLine
                                      }
                                    >

                                      <View
                                        style={
                                          styles.availableDot
                                        }
                                      />

                                      <Text
                                        style={
                                          styles.availableText
                                        }
                                      >
                                        Available
                                      </Text>

                                    </View>

                                  </View>


                                </View>



                                {/* REAL RENT BUTTON */}

                                <Pressable

                                  style={({
                                    pressed,
                                  }) => [

                                    styles.rentButton,

                                    pressed &&
                                      styles.rentButtonPressed,

                                  ]}

                                  onPress={() =>
                                    rentBike(
                                      bike.bike_id
                                    )
                                  }

                                >

                                  <Text
                                    style={
                                      styles.rentButtonText
                                    }
                                  >
                                    Scan
                                  </Text>


                                  <Ionicons

                                    name="qr-code-outline"

                                    size={16}

                                    color="#FFFFFF"

                                  />

                                </Pressable>


                              </View>

                            )
                          )

                        ) : (

                          <View
                            style={
                              styles.noBikeRow
                            }
                          >

                            <Ionicons

                              name="bicycle-outline"

                              size={20}

                              color="#99948D"

                            />


                            <View>

                              <Text
                                style={
                                  styles.noBikeTitle
                                }
                              >
                                No bikes available
                              </Text>


                              <Text
                                style={
                                  styles.noBikes
                                }
                              >
                                Try another station.
                              </Text>

                            </View>

                          </View>

                        )
                      }


                    </View>

                  )
                }


              </View>

            )
          )

        )}



        <View
          style={
            styles.bottomSpace
          }
        />


      </ScrollView>

    </SafeAreaView>

  );

}



// =========================================================
// STYLES
// =========================================================

const styles =
  StyleSheet.create({

    page: {
      flex: 1,
      backgroundColor: '#F7F5F0',
    },


    content: {
      paddingHorizontal: 20,
      paddingTop: 24,
    },


    // =====================================================
    // HEADER
    // =====================================================

    header: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      marginBottom: 21,
    },


    headerText: {
      flex: 1,
      paddingRight: 15,
    },


    brand: {
      color: '#E63946',
      fontSize: 10,
      fontWeight: '900',
      letterSpacing: 2.3,
      marginBottom: 7,
    },


    welcome: {
      color: '#77736D',
      fontSize: 12,
      fontWeight: '600',
      marginBottom: 2,
    },


    heading: {
      color: '#151515',
      fontSize: 27,
      fontWeight: '800',
      letterSpacing: -0.7,
    },


    profileButton: {
      width: 45,
      height: 45,
      borderRadius: 23,
      backgroundColor: '#E63946',
      alignItems: 'center',
      justifyContent: 'center',
    },


    profileInitial: {
      color: '#FFFFFF',
      fontSize: 16,
      fontWeight: '900',
    },


    connectionRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginTop: 8,
    },


    connectionDot: {
      width: 7,
      height: 7,
      borderRadius: 4,
      marginRight: 6,
    },


    connected: {
      backgroundColor: '#25824A',
    },


    connecting: {
      backgroundColor: '#D39B2A',
    },


    connectionText: {
      fontSize: 10,
      color: '#77736D',
    },


    // =====================================================
    // MAP
    // =====================================================

    mapCard: {
      height: 290,
      overflow: 'hidden',
      borderRadius: 20,
      backgroundColor: '#E7E3DD',
      borderWidth: 1,
      borderColor: '#DDD9D2',
    },


    map: {
      width: '100%',
      height: '100%',
    },


    mapLoading: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      padding: 30,
    },


    mapLoadingTitle: {
      marginTop: 10,
      fontSize: 16,
      fontWeight: '800',
      color: '#151515',
    },


    mapLoadingText: {
      marginTop: 8,
      color: '#77736D',
      fontSize: 12,
      textAlign: 'center',
      lineHeight: 18,
    },


    locationButton: {
      marginTop: 15,
      backgroundColor: '#151515',
      borderRadius: 10,
      paddingHorizontal: 17,
      paddingVertical: 9,
    },


    locationButtonText: {
      color: '#FFFFFF',
      fontSize: 11,
      fontWeight: '800',
    },


    mapNote: {
      marginTop: 9,
      color: '#918C85',
      fontSize: 10,
      lineHeight: 15,
    },


    // =====================================================
    // SCAN
    // =====================================================

    scanButton: {
      height: 55,
      marginTop: 19,
      borderRadius: 15,
      backgroundColor: '#E63946',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 9,
    },


    scanButtonPressed: {
      opacity: 0.82,
    },


    scanButtonText: {
      color: '#FFFFFF',
      fontSize: 15,
      fontWeight: '800',
    },


    // =====================================================
    // STATIONS
    // =====================================================

    sectionHeader: {
      marginTop: 29,
      marginBottom: 13,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },


    sectionTitle: {
      color: '#151515',
      fontSize: 21,
      fontWeight: '800',
    },


    sectionMeta: {
      color: '#8D8982',
      fontSize: 12,
    },


    stationLoader: {
      marginTop: 30,
    },


    stationCard: {
      backgroundColor: '#FFFFFF',
      borderWidth: 1,
      borderColor: '#E2DED7',
      borderRadius: 17,
      padding: 15,
      marginBottom: 10,
    },


    stationTop: {
      flexDirection: 'row',
      alignItems: 'center',
    },


    stationIcon: {
      width: 43,
      height: 43,
      borderRadius: 13,
      backgroundColor: '#FFF0F1',
      alignItems: 'center',
      justifyContent: 'center',
    },


    stationInfo: {
      flex: 1,
      marginLeft: 13,
    },


    stationName: {
      color: '#151515',
      fontSize: 15,
      fontWeight: '800',
    },


    stationDetails: {
      color: '#77736D',
      fontSize: 11,
      marginTop: 4,
    },


    stationExpanded: {
      marginTop: 15,
      paddingTop: 13,
      borderTopWidth: 1,
      borderTopColor: '#EFECE7',
    },


    // =====================================================
    // BIKE
    // =====================================================

    bikeCard: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingVertical: 9,
    },


    bikeLeft: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
    },


    bikeIcon: {
      width: 42,
      height: 42,
      borderRadius: 12,
      backgroundColor: '#FFF0F1',
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: 11,
    },


    bikeName: {
      color: '#151515',
      fontSize: 14,
      fontWeight: '800',
    },


    bikeSlot: {
      marginTop: 2,
      color: '#8A8680',
      fontSize: 9,
    },


    availableLine: {
      flexDirection: 'row',
      alignItems: 'center',
      marginTop: 4,
    },


    availableDot: {
      width: 5,
      height: 5,
      borderRadius: 3,
      backgroundColor: '#257C45',
      marginRight: 5,
    },


    availableText: {
      color: '#257C45',
      fontSize: 9,
      fontWeight: '700',
    },


    // =====================================================
    // RENT
    // =====================================================

    rentButton: {
      minWidth: 78,
      height: 39,
      borderRadius: 11,
      backgroundColor: '#E63946',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      paddingHorizontal: 12,
    },


    rentButtonPressed: {
      opacity: 0.78,
    },


    rentButtonText: {
      color: '#FFFFFF',
      fontSize: 12,
      fontWeight: '800',
    },


    // =====================================================
    // NO BIKE
    // =====================================================

    noBikeRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 10,
      paddingVertical: 7,
    },


    noBikeTitle: {
      color: '#55514C',
      fontSize: 12,
      fontWeight: '700',
    },


    noBikes: {
      color: '#99948D',
      fontSize: 10,
      marginTop: 2,
    },


    bottomSpace: {
      height: 40,
    },

  });