import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Linking, Modal, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import { API_BASE_URL, apiFetch } from '../services/api';

// Report identification only: this component never calls the rental endpoint.
export function ReportBikeScanner({ onSelect, onClose }: { onSelect: (bikeId: string) => void; onClose: () => void }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const locked = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function scan(result: BarcodeScanningResult) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/bike-by-qr`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qr_token: result.data.trim(), purpose: 'report' }),
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.bike?.bike_id) throw new Error(data.message || 'This QR could not identify a bike.');
      if (mounted.current) onSelect(data.bike.bike_id);
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : 'Could not check the QR. Try again.');
    } finally { if (mounted.current) setBusy(false); }
  }
  return <Modal animationType="slide" onRequestClose={onClose}>
    <SafeAreaView style={styles.page}>
      <Text style={styles.title}>Scan to report</Text>
      <Text style={styles.hint}>Scan the bike’s QR, then describe the problem. This will not start a ride.</Text>
      {!permission ? <ActivityIndicator /> : !permission.granted ? <View style={styles.permission}>
        <Text style={styles.hint}>Camera access is needed to scan. You can also close this screen and enter the printed bike ID.</Text>
        <Pressable style={styles.button} onPress={() => permission.canAskAgain ? requestPermission() : Linking.openSettings()}>
          <Text style={styles.buttonText}>{permission.canAskAgain ? 'Allow camera' : 'Open settings'}</Text>
        </Pressable>
      </View> : <CameraView style={styles.camera} facing="back" barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={busy || error ? undefined : scan} onMountError={() => setError('Camera could not open. Close and enter the printed bike ID.')} />}
      {busy && <ActivityIndicator color="#303030" />}
      {!!error && <><Text accessibilityRole="alert" style={styles.hint}>{error}</Text>
        <Pressable style={styles.button} onPress={() => { locked.current = false; setError(''); }}><Text style={styles.buttonText}>Scan again</Text></Pressable></>}
      <Pressable style={styles.button} onPress={onClose}><Text style={styles.buttonText}>Cancel scan</Text></Pressable>
    </SafeAreaView>
  </Modal>;
}
const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#F7F5F0', padding: 20, gap: 16 },
  title: { fontSize: 24, fontWeight: '800', color: '#151515', marginTop: 20 },
  hint: { color: '#55514C', fontSize: 14, lineHeight: 21 },
  camera: { flex: 1, minHeight: 220 }, permission: { flex: 1, justifyContent: 'center', gap: 20 },
  button: { padding: 16, backgroundColor: '#E6E4DE', borderRadius: 12, alignItems: 'center' },
  buttonText: { color: '#303030', fontSize: 14, fontWeight: '700' },
});
