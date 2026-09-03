import { useEffect, useState } from 'react';

import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';

import { router } from 'expo-router';

import AsyncStorage from '@react-native-async-storage/async-storage';

import { Ionicons } from '@expo/vector-icons';

import { API_BASE_URL } from '../services/api';


type Student = {
  student_id: string;
  name: string;
  email: string | null;
};


export default function LoginScreen() {

  const [studentId, setStudentId] = useState('');

  const [loading, setLoading] = useState(false);

  const [checkingLogin, setCheckingLogin] = useState(true);

  const [error, setError] = useState('');


  useEffect(() => {
    checkExistingLogin();
  }, []);


  // =====================================================
  // CHECK SAVED LOGIN
  // =====================================================

  async function checkExistingLogin() {


    try {

      const savedStudent =
        await AsyncStorage.getItem(
          'campusbike_student'
        );


      if (savedStudent) {

        router.replace('/(tabs)');

        return;

      }

    } catch (error) {

      console.log(
        'Saved login error:',
        error
      );

    } finally {

      setCheckingLogin(false);

    }

  }


  // =====================================================
  // LOGIN
  // =====================================================

  async function login() {

    const cleanId =
      studentId.trim().toUpperCase();


    if (!cleanId) {

      setError(
        'Enter your student ID.'
      );

      return;

    }


    setLoading(true);
    setError('');


    try {

      const response = await fetch(
        `${API_BASE_URL}/api/dev-login`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify({
            student_id: cleanId,
          }),
        }
      );


      const data =
        await response.json();


      if (!response.ok || !data.success) {

        setError(
          data.message ||
          'Unable to sign in.'
        );

        return;

      }


      const student: Student =
        data.student;


      await AsyncStorage.setItem(
        'campusbike_student',
        JSON.stringify(student)
      );


      console.log(
        'Logged in student:',
        student
      );


      router.replace('/(tabs)');


    } catch (error) {

      console.log(
        'Login error:',
        error
      );


      setError(
        'Could not connect to CampusBike.'
      );

    } finally {

      setLoading(false);

    }

  }


  // =====================================================
  // STARTUP CHECK
  // =====================================================

  if (checkingLogin) {

    return (

      <SafeAreaView style={styles.loadingPage}>

        <ActivityIndicator
          size="small"
          color="#E63946"
        />

      </SafeAreaView>

    );

  }


  // =====================================================
  // LOGIN SCREEN
  // =====================================================

  return (

    <SafeAreaView style={styles.page}>

      <KeyboardAvoidingView

        style={styles.keyboard}

        behavior={
          Platform.OS === 'ios'
            ? 'padding'
            : undefined
        }

      >

        <View style={styles.container}>


          {/* BRAND */}

          <View style={styles.brandArea}>

            <View style={styles.logoBox}>

              <Ionicons
                name="bicycle"
                size={34}
                color="#FFFFFF"
              />

            </View>


            <Text style={styles.brand}>
              CAMPUSBIKE
            </Text>


            <Text style={styles.title}>
              Your campus.
              {'\n'}
              Your ride.
            </Text>


            <Text style={styles.subtitle}>
              Find a bike and get moving.
            </Text>

          </View>



          {/* LOGIN CARD */}

          <View style={styles.card}>

            <Text style={styles.cardTitle}>
              Student Login
            </Text>


            <Text style={styles.cardDescription}>
              Enter your registered student ID.
            </Text>


            <Text style={styles.label}>
              STUDENT ID
            </Text>


            <View
              style={[
                styles.inputBox,

                error
                  ? styles.inputError
                  : null
              ]}
            >

              <Ionicons
                name="person-outline"
                size={19}
                color="#77736D"
              />


              <TextInput

                style={styles.input}

                placeholder="STU001"

                placeholderTextColor="#AAA59D"

                value={studentId}

                onChangeText={(text) => {

                  setStudentId(text);

                  if (error) {
                    setError('');
                  }

                }}

                autoCapitalize="characters"

                autoCorrect={false}

                returnKeyType="go"

                onSubmitEditing={login}

              />

            </View>


            {error ? (

              <Text style={styles.errorText}>
                {error}
              </Text>

            ) : null}


            <Pressable

              style={({ pressed }) => [

                styles.loginButton,

                pressed &&
                styles.loginButtonPressed,

                loading &&
                styles.loginButtonDisabled,

              ]}

              onPress={login}

              disabled={loading}

            >

              {loading ? (

                <ActivityIndicator
                  color="#FFFFFF"
                />

              ) : (

                <>

                  <Text
                    style={
                      styles.loginButtonText
                    }
                  >
                    Continue
                  </Text>


                  <Ionicons
                    name="arrow-forward"
                    size={18}
                    color="#FFFFFF"
                  />

                </>

              )}

            </Pressable>


            <Text style={styles.devNote}>
              Developer login · Google/college verification will replace this before release.
            </Text>

          </View>


        </View>

      </KeyboardAvoidingView>

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


  loadingPage: {

    flex: 1,

    backgroundColor: '#F7F5F0',

    alignItems: 'center',

    justifyContent: 'center',

  },


  keyboard: {

    flex: 1,

  },


  container: {

    flex: 1,

    paddingHorizontal: 24,

    justifyContent: 'center',

  },


  brandArea: {

    marginBottom: 38,

  },


  logoBox: {

    width: 58,

    height: 58,

    borderRadius: 18,

    backgroundColor: '#E63946',

    alignItems: 'center',

    justifyContent: 'center',

    marginBottom: 22,

  },


  brand: {

    color: '#E63946',

    fontSize: 11,

    fontWeight: '900',

    letterSpacing: 2.6,

    marginBottom: 9,

  },


  title: {

    color: '#151515',

    fontSize: 38,

    lineHeight: 42,

    fontWeight: '800',

    letterSpacing: -1.2,

  },


  subtitle: {

    marginTop: 12,

    color: '#77736D',

    fontSize: 14,

  },


  card: {

    backgroundColor: '#FFFFFF',

    borderRadius: 22,

    padding: 20,

    borderWidth: 1,

    borderColor: '#E3DFD8',

  },


  cardTitle: {

    color: '#151515',

    fontSize: 21,

    fontWeight: '800',

  },


  cardDescription: {

    color: '#77736D',

    fontSize: 12,

    marginTop: 5,

    marginBottom: 22,

  },


  label: {

    color: '#77736D',

    fontSize: 9,

    fontWeight: '800',

    letterSpacing: 1.3,

    marginBottom: 8,

  },


  inputBox: {

    minHeight: 54,

    borderWidth: 1,

    borderColor: '#DDD9D2',

    borderRadius: 14,

    flexDirection: 'row',

    alignItems: 'center',

    paddingHorizontal: 15,

    backgroundColor: '#FAF9F7',

  },


  inputError: {

    borderColor: '#E63946',

  },


  input: {

    flex: 1,

    marginLeft: 10,

    color: '#151515',

    fontSize: 15,

    fontWeight: '600',

  },


  errorText: {

    marginTop: 8,

    color: '#D5303C',

    fontSize: 11,

  },


  loginButton: {

    minHeight: 54,

    borderRadius: 14,

    backgroundColor: '#E63946',

    marginTop: 18,

    flexDirection: 'row',

    alignItems: 'center',

    justifyContent: 'center',

    gap: 8,

  },


  loginButtonPressed: {

    opacity: 0.88,

  },


  loginButtonDisabled: {

    opacity: 0.65,

  },


  loginButtonText: {

    color: '#FFFFFF',

    fontSize: 15,

    fontWeight: '800',

  },


  devNote: {

    color: '#AAA59D',

    fontSize: 9,

    lineHeight: 14,

    textAlign: 'center',

    marginTop: 15,

  },

});