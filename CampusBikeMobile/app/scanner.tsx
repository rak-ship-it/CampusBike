import { useEffect, useState } from 'react';

import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from 'react-native';

import {
  CameraView,
  useCameraPermissions,
  BarcodeScanningResult,
} from 'expo-camera';

import {
  router,
} from 'expo-router';

import { Ionicons } from '@expo/vector-icons';

import AsyncStorage from '@react-native-async-storage/async-storage';

import { API_BASE_URL, apiFetch } from '../services/api';


type Student = {
  student_id: string;
  name: string;
  email: string | null;
};


export default function ScannerScreen() {

  // QR-first rental:
  // The student scans any available physical bike.
  // CampusBike identifies the bike from its secure QR.


  const [permission, requestPermission] =
    useCameraPermissions();


  const [student, setStudent] =
    useState<Student | null>(null);


  const [scanned, setScanned] =
    useState(false);


  const [processing, setProcessing] =
    useState(false);


  const [message, setMessage] =
    useState('');


  const [success, setSuccess] =
    useState(false);


  const [detectedBike, setDetectedBike] =
    useState('');


  useEffect(() => {
    loadStudent();
  }, []);


  // =====================================================
  // LOAD STUDENT
  // =====================================================

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
        'Scanner student error:',
        error
      );

    }

  }


  // =====================================================
  // RENT BIKE
  // =====================================================

  async function startRide(
    bikeId: string,
    qrToken: string
  ) {

    if (!student) {
      return;
    }


    setMessage(
      `Starting ride with ${bikeId}...`
    );


    const response = await apiFetch(
      `${API_BASE_URL}/api/rent`,
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

          qr_token:
            qrToken,

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
        'Could not start ride.'
      );

    }


    setDetectedBike(bikeId);

    setSuccess(true);

    setMessage(
      `${bikeId} rented successfully`
    );


    setTimeout(() => {

      router.replace(
        '/(tabs)/ride'
      );

    }, 1200);

  }


  // =====================================================
  // QR SCANNED
  // =====================================================

  async function handleBarcodeScanned(
    result: BarcodeScanningResult
  ) {

    if (
      scanned ||
      processing ||
      !student
    ) {
      return;
    }


    setScanned(true);

    setProcessing(true);

    setSuccess(false);

    setMessage(
      'Checking QR code...'
    );


    const qrToken =
      result.data.trim();


    try {

      // =================================================
      // IDENTIFY BIKE FROM QR
      // Student does not select a bike number first.
      // =================================================

      setMessage(
        'Identifying bike...'
      );


      const identifyResponse =
        await apiFetch(
          `${API_BASE_URL}/api/bike-by-qr`,
          {
            method: 'POST',

            headers: {
              'Content-Type':
                'application/json',
            },

            body: JSON.stringify({
              qr_token: qrToken,
            }),

          }
        );


      const identifyData =
        await identifyResponse.json();


      if (
        !identifyResponse.ok ||
        !identifyData.success
      ) {

        throw new Error(
          identifyData.message ||
          'Bike could not be identified.'
        );

      }


      const bikeId =
        identifyData.bike.bike_id;


      setDetectedBike(
        bikeId
      );


      setMessage(
        `${bikeId} found. Starting ride...`
      );


      await startRide(
        bikeId,
        qrToken
      );


    } catch (error: any) {

      console.log(
        'Scanner error:',
        error
      );


      setSuccess(false);


      setMessage(
        error?.message ||
        'Could not start the ride.'
      );


    } finally {

      setProcessing(false);

    }

  }


  // =====================================================
  // CAMERA PERMISSION LOADING
  // =====================================================

  if (!permission) {

    return (

      <SafeAreaView style={styles.page}>

        <View style={styles.center}>

          <ActivityIndicator
            color="#E63946"
          />

        </View>

      </SafeAreaView>

    );

  }


  // =====================================================
  // CAMERA PERMISSION
  // =====================================================

  if (!permission.granted) {

    return (

      <SafeAreaView style={styles.permissionPage}>

        <View style={styles.permissionIcon}>

          <Ionicons
            name="camera-outline"
            size={35}
            color="#E63946"
          />

        </View>


        <Text style={styles.permissionTitle}>
          Camera access needed
        </Text>


        <Text style={styles.permissionText}>
          CampusBike uses the camera to scan the QR code on a bike.
        </Text>


        <Pressable
          style={styles.permissionButton}
          onPress={requestPermission}
        >

          <Text style={styles.permissionButtonText}>
            Allow camera
          </Text>

        </Pressable>


        <Pressable
          style={styles.cancelButton}
          onPress={() => router.back()}
        >

          <Text style={styles.cancelText}>
            Cancel
          </Text>

        </Pressable>

      </SafeAreaView>

    );

  }


  // =====================================================
  // SCANNER
  // =====================================================

  return (

    <View style={styles.page}>


      <CameraView

        style={styles.camera}

        facing="back"

        barcodeScannerSettings={{
          barcodeTypes: ['qr'],
        }}

        onBarcodeScanned={
          scanned
            ? undefined
            : handleBarcodeScanned
        }

      />


      <View style={styles.overlay}>


        {/* HEADER */}

        <SafeAreaView>

          <View style={styles.header}>

            <Pressable
              style={styles.closeButton}
              onPress={() => router.back()}
            >

              <Ionicons
                name="close"
                size={24}
                color="#FFFFFF"
              />

            </Pressable>


            <View style={styles.headerCenter}>

              <Text style={styles.headerTitle}>
                Scan a bike
              </Text>


              <Text style={styles.headerSubtitle}>

                {
                  detectedBike
                    ? detectedBike
                    : 'CampusBike QR'
                }

              </Text>

            </View>


            <View style={styles.headerSpace} />

          </View>

        </SafeAreaView>



        {/* QR FRAME */}

        <View style={styles.scannerArea}>


          <View style={styles.frame}>


            <View
              style={[
                styles.corner,
                styles.topLeft,
              ]}
            />


            <View
              style={[
                styles.corner,
                styles.topRight,
              ]}
            />


            <View
              style={[
                styles.corner,
                styles.bottomLeft,
              ]}
            />


            <View
              style={[
                styles.corner,
                styles.bottomRight,
              ]}
            />


          </View>


          <Text style={styles.instruction}>

            Scan the QR code on the bike you want to ride

          </Text>


        </View>



        {/* STATUS */}

        <SafeAreaView>

          <View style={styles.bottomArea}>


            {message ? (

              <View
                style={[
                  styles.messageCard,

                  success &&
                  styles.successCard,
                ]}
              >


                {processing ? (

                  <ActivityIndicator
                    color="#E63946"
                  />

                ) : (

                  <Ionicons

                    name={
                      success
                        ? 'checkmark-circle'
                        : 'alert-circle-outline'
                    }

                    size={23}

                    color={
                      success
                        ? '#257C45'
                        : '#E63946'
                    }

                  />

                )}


                <Text
                  style={[
                    styles.messageText,

                    success &&
                    styles.successText,
                  ]}
                >

                  {message}

                </Text>


              </View>

            ) : null}



            {scanned &&
            !processing &&
            !success ? (

              <Pressable

                style={styles.scanAgainButton}

                onPress={() => {

                  setScanned(false);

                  setMessage('');

                  setDetectedBike('');

                }}

              >

                <Ionicons
                  name="scan-outline"
                  size={19}
                  color="#FFFFFF"
                />


                <Text style={styles.scanAgainText}>
                  Scan again
                </Text>

              </Pressable>

            ) : null}


          </View>

        </SafeAreaView>


      </View>


    </View>

  );

}


// =========================================================
// STYLES
// =========================================================

const styles = StyleSheet.create({

  page: {
    flex: 1,
    backgroundColor: '#000000',
  },


  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },


  camera: {
    ...StyleSheet.absoluteFillObject,
  },


  overlay: {
    flex: 1,
    backgroundColor:
      'rgba(0,0,0,0.28)',
    justifyContent: 'space-between',
  },


  header: {
    paddingHorizontal: 20,
    marginTop: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent:
      'space-between',
  },


  closeButton: {
    width: 43,
    height: 43,
    borderRadius: 22,
    backgroundColor:
      'rgba(0,0,0,0.55)',
    alignItems: 'center',
    justifyContent: 'center',
  },


  headerCenter: {
    alignItems: 'center',
  },


  headerTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '800',
  },


  headerSubtitle: {
    color: '#E5E5E5',
    fontSize: 11,
    fontWeight: '600',
    marginTop: 2,
  },


  headerSpace: {
    width: 43,
  },


  scannerArea: {
    alignItems: 'center',
  },


  frame: {
    width: 245,
    height: 245,
    position: 'relative',
  },


  corner: {
    position: 'absolute',
    width: 48,
    height: 48,
    borderColor: '#FFFFFF',
  },


  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
    borderTopLeftRadius: 15,
  },


  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
    borderTopRightRadius: 15,
  },


  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderBottomLeftRadius: 15,
  },


  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderBottomRightRadius: 15,
  },


  instruction: {
    marginTop: 25,
    paddingHorizontal: 45,
    color: '#FFFFFF',
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
    fontWeight: '600',
  },


  bottomArea: {
    paddingHorizontal: 20,
    paddingBottom: 22,
  },


  messageCard: {
    minHeight: 58,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
    paddingVertical: 13,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },


  successCard: {
    backgroundColor: '#EDF7F0',
  },


  messageText: {
    flex: 1,
    color: '#151515',
    fontSize: 12,
    fontWeight: '700',
  },


  successText: {
    color: '#257C45',
  },


  scanAgainButton: {
    height: 52,
    marginTop: 12,
    borderRadius: 14,
    backgroundColor: '#E63946',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },


  scanAgainText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },


  permissionPage: {
    flex: 1,
    paddingHorizontal: 30,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F7F5F0',
  },


  permissionIcon: {
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: '#FFF0F1',
    alignItems: 'center',
    justifyContent: 'center',
  },


  permissionTitle: {
    marginTop: 20,
    color: '#151515',
    fontSize: 21,
    fontWeight: '800',
  },


  permissionText: {
    marginTop: 8,
    color: '#77736D',
    fontSize: 12,
    lineHeight: 18,
    textAlign: 'center',
  },


  permissionButton: {
    marginTop: 25,
    height: 52,
    paddingHorizontal: 27,
    borderRadius: 14,
    backgroundColor: '#E63946',
    alignItems: 'center',
    justifyContent: 'center',
  },


  permissionButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },


  cancelButton: {
    marginTop: 15,
  },


  cancelText: {
    color: '#77736D',
    fontSize: 12,
    fontWeight: '700',
  },

});