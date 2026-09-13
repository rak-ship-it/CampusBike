import { useCallback, useState } from 'react';

import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  RefreshControl,
} from 'react-native';

import { Ionicons } from '@expo/vector-icons';

import {
  router,
  useFocusEffect,
} from 'expo-router';

import AsyncStorage from '@react-native-async-storage/async-storage';

import { API_BASE_URL, apiFetch } from '../../services/api';


type Student = {
  student_id: string;
  name: string;
  email: string | null;
};


type Ride = {
  ride_id: number;
  bike_id: string;
  student_id: string;
  rented_at: string | null;
  returned_at: string | null;
  start_station: string | null;
  start_slot: string | null;
  return_station: string | null;
  return_slot: string | null;
  rent_method: string | null;
  qr_verified: number;
};


export default function HistoryScreen() {

  const [student, setStudent] =
    useState<Student | null>(null);

  const [rides, setRides] =
    useState<Ride[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [error, setError] =
    useState('');


  useFocusEffect(

    useCallback(() => {

      loadHistory();

    }, [])

  );


  async function loadHistory() {

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


      const response = await apiFetch(
        `${API_BASE_URL}/api/students/${studentData.student_id}/rides`
      );


      const data =
        await response.json();


      if (
        !response.ok ||
        !data.success
      ) {

        throw new Error(
          data.message ||
          'Could not load ride history.'
        );

      }


      setRides(
        data.rides || []
      );


    } catch (error: any) {

      console.log(
        'History error:',
        error
      );


      setError(
        error?.message ||
        'Could not connect to CampusBike.'
      );


    } finally {

      setLoading(false);
      setRefreshing(false);

    }

  }


  async function refresh() {

    setRefreshing(true);

    await loadHistory();

  }


  function getDuration(
    start: string | null,
    end: string | null
  ) {

    if (!start || !end) {
      return '—';
    }


    const startDate =
      new Date(
        start.replace(' ', 'T')
      );


    const endDate =
      new Date(
        end.replace(' ', 'T')
      );


    const difference =
      endDate.getTime() -
      startDate.getTime();


    if (difference <= 0) {
      return '—';
    }


    const totalMinutes =
      Math.floor(
        difference / 60000
      );


    const hours =
      Math.floor(
        totalMinutes / 60
      );


    const minutes =
      totalMinutes % 60;


    if (hours > 0) {

      return `${hours}h ${minutes}m`;

    }


    if (minutes === 0) {

      return '< 1 min';

    }


    return `${minutes} min`;

  }


  function formatDate(
    value: string | null
  ) {

    if (!value) {
      return '—';
    }


    const date =
      new Date(
        value.replace(' ', 'T')
      );


    return date.toLocaleString(
      'en-IN',
      {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      }
    );

  }


  if (loading) {

    return (

      <SafeAreaView style={styles.page}>

        <View style={styles.center}>

          <ActivityIndicator
            color="#E63946"
          />

          <Text style={styles.loadingText}>
            Loading your rides...
          </Text>

        </View>

      </SafeAreaView>

    );

  }


  return (

    <SafeAreaView style={styles.page}>

      <ScrollView

        contentContainerStyle={styles.content}

        showsVerticalScrollIndicator={false}

        refreshControl={

          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            tintColor="#E63946"
          />

        }

      >


        <Text style={styles.brand}>
          CAMPUSBIKE
        </Text>


        <Text style={styles.title}>
          Ride History
        </Text>


        <Text style={styles.subtitle}>

          {student?.name
            ? `${student.name}'s completed rides`
            : 'Your completed rides'}

        </Text>



        {/* SUMMARY */}

        <View style={styles.summaryCard}>

          <View style={styles.summaryIcon}>

            <Ionicons
              name="bicycle"
              size={25}
              color="#E63946"
            />

          </View>


          <View>

            <Text style={styles.summaryLabel}>
              TOTAL RIDES
            </Text>


            <Text style={styles.summaryNumber}>
              {rides.length}
            </Text>

          </View>

        </View>



        {error ? (

          <View style={styles.emptyCard}>

            <Ionicons
              name="cloud-offline-outline"
              size={35}
              color="#E63946"
            />


            <Text style={styles.emptyTitle}>
              Couldn&apos;t load history
            </Text>


            <Text style={styles.emptyText}>
              {error}
            </Text>

          </View>


        ) : rides.length === 0 ? (

          <View style={styles.emptyCard}>

            <View style={styles.emptyIcon}>

              <Ionicons
                name="time-outline"
                size={38}
                color="#E63946"
              />

            </View>


            <Text style={styles.emptyTitle}>
              No rides yet
            </Text>


            <Text style={styles.emptyText}>
              Your completed CampusBike rides will appear here.
            </Text>

          </View>


        ) : (

          rides.map((ride) => (

            <View
              key={ride.ride_id}
              style={styles.rideCard}
            >


              <View style={styles.rideHeader}>


                <View>

                  <Text style={styles.rideBike}>
                    {ride.bike_id}
                  </Text>


                  <Text style={styles.rideNumber}>
                    Ride #{ride.ride_id}
                  </Text>

                </View>


                <View style={styles.completedBadge}>

                  <Ionicons
                    name="checkmark-circle"
                    size={13}
                    color="#257C45"
                  />


                  <Text style={styles.completedText}>
                    COMPLETED
                  </Text>

                </View>


              </View>



              <View style={styles.route}>


                <View style={styles.routePoint}>

                  <View style={styles.startDot} />

                  <View style={styles.routeContent}>

                    <Text style={styles.routeLabel}>
                      FROM
                    </Text>


                    <Text style={styles.routeStation}>
                      {ride.start_station || 'Unknown station'}
                    </Text>


                    <Text style={styles.routeMeta}>
                      {ride.start_slot || '—'}
                    </Text>

                  </View>

                </View>



                <View style={styles.routeLine} />



                <View style={styles.routePoint}>

                  <View style={styles.endDot} />

                  <View style={styles.routeContent}>

                    <Text style={styles.routeLabel}>
                      TO
                    </Text>


                    <Text style={styles.routeStation}>
                      {ride.return_station || 'Unknown station'}
                    </Text>


                    <Text style={styles.routeMeta}>
                      {ride.return_slot || '—'}
                    </Text>

                  </View>

                </View>


              </View>



              <View style={styles.divider} />



              <View style={styles.detailsRow}>


                <View style={styles.detail}>

                  <Ionicons
                    name="calendar-outline"
                    size={15}
                    color="#8D8982"
                  />


                  <View>

                    <Text style={styles.detailLabel}>
                      STARTED
                    </Text>

                    <Text style={styles.detailValue}>
                      {formatDate(
                        ride.rented_at
                      )}
                    </Text>

                  </View>

                </View>



                <View style={styles.detail}>

                  <Ionicons
                    name="time-outline"
                    size={15}
                    color="#8D8982"
                  />


                  <View>

                    <Text style={styles.detailLabel}>
                      DURATION
                    </Text>

                    <Text style={styles.detailValue}>
                      {getDuration(
                        ride.rented_at,
                        ride.returned_at
                      )}
                    </Text>

                  </View>

                </View>


              </View>


            </View>

          ))

        )}


        <View style={styles.bottomSpace} />

      </ScrollView>

    </SafeAreaView>

  );

}


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
    marginBottom: 22,
  },


  summaryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#E2DED7',
    padding: 17,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 18,
  },


  summaryIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: '#FFF0F1',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 13,
  },


  summaryLabel: {
    color: '#99948D',
    fontSize: 8,
    fontWeight: '900',
    letterSpacing: 1.1,
  },


  summaryNumber: {
    marginTop: 2,
    color: '#151515',
    fontSize: 23,
    fontWeight: '900',
  },


  rideCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 19,
    borderWidth: 1,
    borderColor: '#E2DED7',
    padding: 17,
    marginBottom: 12,
  },


  rideHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },


  rideBike: {
    color: '#151515',
    fontSize: 18,
    fontWeight: '900',
  },


  rideNumber: {
    marginTop: 2,
    color: '#99948D',
    fontSize: 9,
    fontWeight: '600',
  },


  completedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#EDF7F0',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },


  completedText: {
    color: '#257C45',
    fontSize: 7,
    fontWeight: '900',
  },


  route: {
    marginTop: 19,
  },


  routePoint: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },


  startDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#E63946',
    marginTop: 5,
    marginRight: 12,
  },


  endDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: '#151515',
    marginTop: 5,
    marginRight: 12,
  },


  routeLine: {
    width: 1,
    height: 24,
    backgroundColor: '#D9D5CF',
    marginLeft: 4.5,
  },


  routeContent: {
    flex: 1,
  },


  routeLabel: {
    color: '#AAA59D',
    fontSize: 7,
    fontWeight: '900',
    letterSpacing: 1,
  },


  routeStation: {
    color: '#151515',
    fontSize: 13,
    fontWeight: '800',
    marginTop: 2,
  },


  routeMeta: {
    color: '#8D8982',
    fontSize: 9,
    marginTop: 2,
  },


  divider: {
    height: 1,
    backgroundColor: '#EFECE7',
    marginVertical: 15,
  },


  detailsRow: {
    flexDirection: 'row',
  },


  detail: {
    width: '50%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },


  detailLabel: {
    color: '#AAA59D',
    fontSize: 7,
    fontWeight: '900',
  },


  detailValue: {
    color: '#55514C',
    fontSize: 9,
    fontWeight: '700',
    marginTop: 1,
  },


  emptyCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#E2DED7',
    padding: 30,
    alignItems: 'center',
  },


  emptyIcon: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#FFF0F1',
    alignItems: 'center',
    justifyContent: 'center',
  },


  emptyTitle: {
    marginTop: 17,
    color: '#151515',
    fontSize: 19,
    fontWeight: '800',
  },


  emptyText: {
    marginTop: 6,
    color: '#77736D',
    fontSize: 11,
    lineHeight: 17,
    textAlign: 'center',
  },


  bottomSpace: {
    height: 40,
  },

});
