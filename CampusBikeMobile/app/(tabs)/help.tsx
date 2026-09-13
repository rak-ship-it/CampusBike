import { useCallback, useState } from 'react';

import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  Alert,
  ActivityIndicator,
} from 'react-native';

import {
  useFocusEffect,
} from 'expo-router';

import AsyncStorage
  from '@react-native-async-storage/async-storage';

import { API_BASE_URL }
  from '../../services/api';


type Student = {
  student_id: string;
  name: string;
  email: string | null;
};


type Bike = {
  bike_id: string;
};


const ISSUE_TYPES = [
  {
    name: 'Brake',
    emoji: '🔧',
  },
  {
    name: 'Tyre',
    emoji: '🛞',
  },
  {
    name: 'Chain',
    emoji: '🔗',
  },
  {
    name: 'Seat',
    emoji: '💺',
  },
  {
    name: 'Lock/Dock',
    emoji: '🔒',
  },
  {
    name: 'QR Code',
    emoji: '▦',
  },
  {
    name: 'Other',
    emoji: '🛠️',
  },
];


export default function HelpScreen() {

  const [student, setStudent] =
    useState<Student | null>(null);

  const [bikes, setBikes] =
    useState<Bike[]>([]);

  const [bikeId, setBikeId] =
    useState('');

  const [issueType, setIssueType] =
    useState('');

  const [description, setDescription] =
    useState('');

  const [severity, setSeverity] =
    useState('Medium');

  const [loading, setLoading] =
    useState(true);

  const [sending, setSending] =
    useState(false);


  useFocusEffect(

    useCallback(() => {

      loadData();

    }, [])

  );


  async function loadData() {

    try {

      const saved =
        await AsyncStorage.getItem(
          'campusbike_student'
        );


      if (!saved) {
        return;
      }


      const studentData: Student =
        JSON.parse(saved);


      setStudent(studentData);


      const [
        stationsResponse,
        activeRideResponse,
      ] = await Promise.all([

        fetch(
          `${API_BASE_URL}/api/stations`
        ),

        fetch(
          `${API_BASE_URL}/api/students/${studentData.student_id}/active-ride`
        ),

      ]);


      const stationsData =
        await stationsResponse.json();


      const activeRideData =
        await activeRideResponse.json();


      const bikeMap:
        Record<string, Bike> = {};


      /*
       * Add bikes currently parked at stations.
       */

      if (Array.isArray(stationsData)) {

        stationsData.forEach(
          (station: any) => {

            const stationBikes =
              station.bikes || [];


            stationBikes.forEach(
              (bike: any) => {

                if (bike.bike_id) {

                  bikeMap[bike.bike_id] = {
                    bike_id:
                      bike.bike_id,
                  };

                }

              }
            );

          }
        );

      }


      /*
       * Also include the student's active bike.
       * This means a student can report a problem
       * while they are actually riding it.
       */

      const activeRide =
        activeRideData?.ride ||
        activeRideData?.active_ride ||
        activeRideData;


      if (
        activeRide?.bike_id
      ) {

        bikeMap[
          activeRide.bike_id
        ] = {
          bike_id:
            activeRide.bike_id,
        };


        setBikeId(
          activeRide.bike_id
        );

      }


      const list =
        Object.values(
          bikeMap
        ).sort(
          (a, b) =>
            a.bike_id.localeCompare(
              b.bike_id
            )
        );


      setBikes(list);


    } catch (error) {

      console.log(
        'Help screen error:',
        error
      );

    } finally {

      setLoading(false);

    }

  }


  async function submitReport() {

    if (!student) {

      Alert.alert(
        'Account unavailable',
        'Please sign in again.'
      );

      return;

    }


    if (!bikeId) {

      Alert.alert(
        'Choose a bike',
        'Select the bike that has the problem.'
      );

      return;

    }


    if (!issueType) {

      Alert.alert(
        'Choose the problem',
        'Select what is wrong with the bike.'
      );

      return;

    }


    setSending(true);


    try {

      const response =
        await fetch(
          `${API_BASE_URL}/api/maintenance-reports`,
          {
            method: 'POST',

            headers: {
              'Content-Type':
                'application/json',
            },

            body: JSON.stringify({

              student_id:
                student.student_id,

              bike_id:
                bikeId,

              issue_type:
                issueType,

              description:
                description.trim(),

              severity:
                severity,

            }),

          }
        );


      const data =
        await response.json();


      if (
        !response.ok ||
        !data.success
      ) {

        throw new Error(
          data.message ||
          'Could not send report.'
        );

      }


      Alert.alert(
        'Report sent',
        `Thanks. ${bikeId} has been reported to the campus team.`
      );


      setIssueType('');
      setDescription('');
      setSeverity('Medium');


      await loadData();


    } catch (error: any) {

      Alert.alert(
        'Could not send report',
        error?.message ||
        'Please try again.'
      );


    } finally {

      setSending(false);

    }

  }


  if (loading) {

    return (

      <SafeAreaView style={styles.page}>

        <View style={styles.loading}>

          <ActivityIndicator
            color="#E63946"
          />

          <Text style={styles.loadingText}>
            Loading...
          </Text>

        </View>

      </SafeAreaView>

    );

  }


  return (

    <SafeAreaView style={styles.page}>

      <ScrollView

        contentContainerStyle={
          styles.content
        }

        showsVerticalScrollIndicator={
          false
        }

      >


        <Text style={styles.brand}>
          CAMPUSBIKE
        </Text>


        <Text style={styles.title}>
          Help
        </Text>


        <Text style={styles.subtitle}>
          Something wrong with a bike? Tell us here.
        </Text>



        {/* REPORT CARD */}

        <View style={styles.card}>


          <View style={styles.cardTitleRow}>

            <View style={styles.toolBox}>

              <Text style={styles.toolEmoji}>
                🔧
              </Text>

            </View>


            <View style={{ flex: 1 }}>

              <Text style={styles.cardTitle}>
                Report a problem
              </Text>


              <Text style={styles.cardSubtitle}>
                Help us keep CampusBike safe and ready.
              </Text>

            </View>

          </View>



          {/* BIKE */}

          <Text style={styles.sectionLabel}>
            BIKE
          </Text>


          {bikes.length === 0 ? (

            <Text style={styles.noBikeText}>
              No bikes available to report right now.
            </Text>

          ) : (

            <View style={styles.optionsWrap}>

              {bikes.map(
                (bike) => (

                  <Pressable

                    key={
                      bike.bike_id
                    }

                    onPress={() =>
                      setBikeId(
                        bike.bike_id
                      )
                    }

                    style={[
                      styles.bikeButton,

                      bikeId ===
                        bike.bike_id &&
                        styles.bikeButtonSelected,
                    ]}

                  >

                    <Text
                      style={[
                        styles.bikeText,

                        bikeId ===
                          bike.bike_id &&
                          styles.bikeTextSelected,
                      ]}
                    >
                      🚲 {bike.bike_id}
                    </Text>

                  </Pressable>

                )
              )}

            </View>

          )}



          {/* ISSUE */}

          <Text style={styles.sectionLabel}>
            WHAT&apos;S WRONG?
          </Text>


          <View style={styles.issueGrid}>

            {ISSUE_TYPES.map(
              (issue) => {

                const selected =
                  issueType ===
                  issue.name;


                return (

                  <Pressable

                    key={
                      issue.name
                    }

                    onPress={() =>
                      setIssueType(
                        issue.name
                      )
                    }

                    style={[
                      styles.issueButton,

                      selected &&
                        styles.issueSelected,
                    ]}

                  >

                    <Text style={styles.issueEmoji}>
                      {issue.emoji}
                    </Text>


                    <Text
                      style={[
                        styles.issueText,

                        selected &&
                          styles.issueTextSelected,
                      ]}
                    >
                      {issue.name}
                    </Text>

                  </Pressable>

                );

              }
            )}

          </View>



          {/* SEVERITY */}

          <Text style={styles.sectionLabel}>
            HOW SERIOUS?
          </Text>


          <View style={styles.severityRow}>

            {[
              'Low',
              'Medium',
              'High',
            ].map(
              (level) => (

                <Pressable

                  key={level}

                  onPress={() =>
                    setSeverity(
                      level
                    )
                  }

                  style={[
                    styles.severityButton,

                    severity ===
                      level &&
                      styles.severitySelected,
                  ]}

                >

                  <Text
                    style={[
                      styles.severityText,

                      severity ===
                        level &&
                        styles.severityTextSelected,
                    ]}
                  >
                    {level}
                  </Text>

                </Pressable>

              )
            )}

          </View>



          {/* DESCRIPTION */}

          <Text style={styles.sectionLabel}>
            DETAILS
          </Text>


          <TextInput

            value={description}

            onChangeText={
              setDescription
            }

            placeholder="Anything else we should know?"

            placeholderTextColor="#AAA59D"

            multiline

            maxLength={500}

            style={styles.input}

          />


          <Text style={styles.characterCount}>
            {description.length}/500
          </Text>



          {/* SEND */}

          <Pressable

            disabled={sending}

            onPress={
              submitReport
            }

            style={({ pressed }) => [

              styles.submitButton,

              pressed && {
                opacity: 0.85,
              },

              sending && {
                opacity: 0.6,
              },

            ]}

          >

            {sending ? (

              <ActivityIndicator
                color="#FFFFFF"
              />

            ) : (

              <Text style={styles.submitText}>
                Send report
              </Text>

            )}

          </Pressable>


        </View>



        {/* SIMPLE HELP INFO */}

        <View style={styles.infoCard}>

          <Text style={styles.infoEmoji}>
            💡
          </Text>


          <View style={{ flex: 1 }}>

            <Text style={styles.infoTitle}>
              Before you ride
            </Text>


            <Text style={styles.infoText}>
              Check the brakes, tyres and seat quickly before starting your ride.
            </Text>

          </View>

        </View>



        <View style={{ height: 40 }} />


      </ScrollView>

    </SafeAreaView>

  );

}


const styles =
  StyleSheet.create({

    page: {
      flex: 1,
      backgroundColor:
        '#F7F5F0',
    },


    content: {
      paddingHorizontal: 20,
      paddingTop: 25,
    },


    loading: {
      flex: 1,
      justifyContent:
        'center',
      alignItems:
        'center',
    },


    loadingText: {
      marginTop: 8,
      color:
        '#77736D',
      fontSize: 12,
    },


    brand: {
      color:
        '#E63946',
      fontSize: 10,
      fontWeight:
        '900',
      letterSpacing: 2.3,
    },


    title: {
      marginTop: 6,
      color:
        '#151515',
      fontSize: 31,
      fontWeight:
        '800',
      letterSpacing:
        -0.8,
    },


    subtitle: {
      marginTop: 5,
      marginBottom: 22,
      color:
        '#77736D',
      fontSize: 12,
    },


    card: {
      backgroundColor:
        '#FFFFFF',
      borderRadius: 20,
      borderWidth: 1,
      borderColor:
        '#E2DED7',
      padding: 18,
    },


    cardTitleRow: {
      flexDirection:
        'row',
      alignItems:
        'center',
      marginBottom: 22,
    },


    toolBox: {
      width: 48,
      height: 48,
      borderRadius: 14,
      backgroundColor:
        '#FFF0F1',
      justifyContent:
        'center',
      alignItems:
        'center',
      marginRight: 12,
    },


    toolEmoji: {
      fontSize: 23,
    },


    cardTitle: {
      color:
        '#151515',
      fontSize: 17,
      fontWeight:
        '800',
    },


    cardSubtitle: {
      marginTop: 3,
      color:
        '#8D8982',
      fontSize: 10,
    },


    sectionLabel: {
      marginTop: 17,
      marginBottom: 9,
      color:
        '#8D8982',
      fontSize: 8,
      fontWeight:
        '900',
      letterSpacing: 1.1,
    },


    optionsWrap: {
      flexDirection:
        'row',
      flexWrap:
        'wrap',
      gap: 8,
    },


    bikeButton: {
      paddingHorizontal: 12,
      paddingVertical: 9,
      borderRadius: 11,
      borderWidth: 1,
      borderColor:
        '#DDD9D2',
      backgroundColor:
        '#FAF9F6',
    },


    bikeButtonSelected: {
      borderColor:
        '#E63946',
      backgroundColor:
        '#FFF0F1',
    },


    bikeText: {
      color:
        '#55514C',
      fontSize: 11,
      fontWeight:
        '700',
    },


    bikeTextSelected: {
      color:
        '#E63946',
    },


    noBikeText: {
      color:
        '#8D8982',
      fontSize: 11,
    },


    issueGrid: {
      flexDirection:
        'row',
      flexWrap:
        'wrap',
      gap: 8,
    },


    issueButton: {
      width: '31%',
      minHeight: 70,
      borderRadius: 13,
      borderWidth: 1,
      borderColor:
        '#E2DED7',
      backgroundColor:
        '#FAF9F6',
      alignItems:
        'center',
      justifyContent:
        'center',
      paddingHorizontal: 4,
    },


    issueSelected: {
      borderColor:
        '#E63946',
      backgroundColor:
        '#FFF0F1',
    },


    issueEmoji: {
      fontSize: 20,
      marginBottom: 5,
    },


    issueText: {
      color:
        '#55514C',
      fontSize: 9,
      fontWeight:
        '700',
      textAlign:
        'center',
    },


    issueTextSelected: {
      color:
        '#E63946',
      fontWeight:
        '900',
    },


    severityRow: {
      flexDirection:
        'row',
      gap: 8,
    },


    severityButton: {
      flex: 1,
      borderRadius: 10,
      borderWidth: 1,
      borderColor:
        '#E2DED7',
      alignItems:
        'center',
      paddingVertical: 10,
    },


    severitySelected: {
      backgroundColor:
        '#151515',
      borderColor:
        '#151515',
    },


    severityText: {
      color:
        '#77736D',
      fontSize: 10,
      fontWeight:
        '700',
    },


    severityTextSelected: {
      color:
        '#FFFFFF',
    },


    input: {
      minHeight: 100,
      borderRadius: 13,
      borderWidth: 1,
      borderColor:
        '#E2DED7',
      backgroundColor:
        '#FAF9F6',
      padding: 13,
      color:
        '#151515',
      fontSize: 12,
      textAlignVertical:
        'top',
    },


    characterCount: {
      marginTop: 5,
      textAlign:
        'right',
      color:
        '#AAA59D',
      fontSize: 8,
    },


    submitButton: {
      marginTop: 18,
      height: 50,
      borderRadius: 14,
      backgroundColor:
        '#E63946',
      justifyContent:
        'center',
      alignItems:
        'center',
    },


    submitText: {
      color:
        '#FFFFFF',
      fontSize: 13,
      fontWeight:
        '900',
    },


    infoCard: {
      marginTop: 13,
      backgroundColor:
        '#FFFFFF',
      borderRadius: 16,
      borderWidth: 1,
      borderColor:
        '#E2DED7',
      padding: 15,
      flexDirection:
        'row',
      alignItems:
        'center',
    },


    infoEmoji: {
      fontSize: 21,
      marginRight: 11,
    },


    infoTitle: {
      color:
        '#151515',
      fontSize: 12,
      fontWeight:
        '800',
    },


    infoText: {
      marginTop: 2,
      color:
        '#77736D',
      fontSize: 9,
      lineHeight: 14,
    },

  });
