import { logoutSession } from '../services/api';
import { useEffect, useState } from 'react';

import {
  Alert,
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from 'react-native';

import { router } from 'expo-router';

import AsyncStorage from '@react-native-async-storage/async-storage';

import { Ionicons } from '@expo/vector-icons';


type Student = {
  student_id: string;
  name: string;
  email: string | null;
};


export default function ProfileScreen() {

  const [student, setStudent] =
    useState<Student | null>(null);

  const [loading, setLoading] =
    useState(true);


  useEffect(() => {
    loadStudent();
  }, []);


  async function loadStudent() {

    try {

      const saved =
        await AsyncStorage.getItem(
          'campusbike_student'
        );

      if (!saved) {

        router.replace('/');

        return;

      }

      setStudent(
        JSON.parse(saved)
      );

    } catch (error) {

      console.log(
        'Profile error:',
        error
      );

    } finally {

      setLoading(false);

    }

  }


  async function logout() {

    try {
      await logoutSession();
      router.replace('/');
    } catch {
      Alert.alert('Could not sign out', 'Check your connection and try again.');
    }

  }


  if (loading) {

    return (

      <SafeAreaView style={styles.loadingPage}>

        <ActivityIndicator
          color="#E63946"
        />

      </SafeAreaView>

    );

  }


  return (

    <SafeAreaView style={styles.page}>

      <View style={styles.container}>


        {/* TOP BAR */}

        <View style={styles.topBar}>

          <Pressable
            style={styles.backButton}
            onPress={() => router.back()}
          >

            <Ionicons
              name="arrow-back"
              size={22}
              color="#151515"
            />

          </Pressable>


          <Text style={styles.topTitle}>
            Profile
          </Text>


          <View style={styles.emptySpace} />

        </View>



        {/* PROFILE */}

        <View style={styles.profileArea}>

          <View style={styles.avatar}>

            <Text style={styles.avatarText}>

              {student?.name
                ?.charAt(0)
                .toUpperCase() || '?'}

            </Text>

          </View>


          <Text style={styles.name}>

            {student?.name}

          </Text>


          <Text style={styles.studentId}>

            {student?.student_id}

          </Text>


          {student?.email ? (

            <Text style={styles.email}>

              {student.email}

            </Text>

          ) : null}

        </View>



        {/* ACCOUNT CARD */}

        <View style={styles.card}>

          <View style={styles.row}>

            <View style={styles.iconBox}>

              <Ionicons
                name="person-outline"
                size={20}
                color="#E63946"
              />

            </View>

            <View>

              <Text style={styles.rowLabel}>
                STUDENT
              </Text>

              <Text style={styles.rowValue}>
                {student?.name}
              </Text>

            </View>

          </View>


          <View style={styles.divider} />


          <View style={styles.row}>

            <View style={styles.iconBox}>

              <Ionicons
                name="card-outline"
                size={20}
                color="#E63946"
              />

            </View>

            <View>

              <Text style={styles.rowLabel}>
                STUDENT ID
              </Text>

              <Text style={styles.rowValue}>
                {student?.student_id}
              </Text>

            </View>

          </View>

        </View>



        {/* LOGOUT */}

        <Pressable
          style={{ paddingVertical: 16, alignItems: 'center' }}
          onPress={() => router.push('/change-password')}
        >
          <Text style={{ color: '#E63946', fontWeight: '700' }}>Change password</Text>
        </Pressable>

        <Pressable
          style={styles.logoutButton}
          onPress={logout}
        >

          <Ionicons
            name="log-out-outline"
            size={20}
            color="#E63946"
          />

          <Text style={styles.logoutText}>
            Log out
          </Text>

        </Pressable>


        <Text style={styles.version}>
          CampusBike
        </Text>


      </View>

    </SafeAreaView>

  );

}


const styles = StyleSheet.create({

  page: {
    flex: 1,
    backgroundColor: '#F7F5F0',
  },

  loadingPage: {
    flex: 1,
    backgroundColor: '#F7F5F0',
    alignItems: 'center',
    justifyContent: 'center',
  },

  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 18,
  },

  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  backButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#E2DED7',
  },

  topTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#151515',
  },

  emptySpace: {
    width: 42,
  },

  profileArea: {
    alignItems: 'center',
    marginTop: 45,
  },

  avatar: {
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: '#E63946',
    alignItems: 'center',
    justifyContent: 'center',
  },

  avatarText: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: '900',
  },

  name: {
    marginTop: 16,
    color: '#151515',
    fontSize: 25,
    fontWeight: '800',
  },

  studentId: {
    marginTop: 5,
    color: '#77736D',
    fontSize: 13,
    fontWeight: '600',
  },

  email: {
    marginTop: 4,
    color: '#99948D',
    fontSize: 12,
  },

  card: {
    marginTop: 40,
    backgroundColor: '#FFFFFF',
    borderRadius: 19,
    paddingHorizontal: 17,
    borderWidth: 1,
    borderColor: '#E2DED7',
  },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 17,
  },

  iconBox: {
    width: 42,
    height: 42,
    borderRadius: 13,
    backgroundColor: '#FFF0F1',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 13,
  },

  rowLabel: {
    color: '#99948D',
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 1.2,
  },

  rowValue: {
    marginTop: 3,
    color: '#151515',
    fontSize: 14,
    fontWeight: '700',
  },

  divider: {
    height: 1,
    backgroundColor: '#EFECE7',
  },

  logoutButton: {
    marginTop: 28,
    height: 54,
    borderRadius: 15,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E8C9CC',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },

  logoutText: {
    color: '#E63946',
    fontSize: 14,
    fontWeight: '800',
  },

  version: {
    marginTop: 18,
    textAlign: 'center',
    color: '#AAA59D',
    fontSize: 10,
  },

});