import { useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput } from 'react-native';
import { router } from 'expo-router';
import { API_BASE_URL, apiFetch, clearSession } from '../services/api';

export default function ChangePasswordScreen() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function changePassword() {
    if (busy) return;
    if (!current || next.length < 12 || next.length > 128 || next !== confirmation || current === next) {
      setError('Enter your current password and a different new password of 12–128 characters. Both new-password fields must match.');
      return;
    }
    setBusy(true); setError('');
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/change-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        setError(data.message || 'Could not change your password.');
        return;
      }
      setCurrent(''); setNext(''); setConfirmation('');
      await clearSession();
      Alert.alert('Password changed', 'Sign in again with your new password. Your ride history is preserved.');
      router.replace('/');
    } catch {
      setError('Could not confirm the result. If the request timed out, try signing in with your new password before trying again.');
    } finally { setBusy(false); }
  }

  return (
    <SafeAreaView style={styles.page}>
      <KeyboardAvoidingView style={styles.page} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Pressable onPress={() => router.back()} disabled={busy}><Text style={styles.link}>← Profile</Text></Pressable>
          <Text style={styles.title}>Change password</Text>
          <Text style={styles.body}>Use a unique password. Changing it signs you out on every device, without deleting your rides.</Text>
          <Text style={styles.label}>Current password</Text>
          <TextInput accessibilityLabel="Current password" style={styles.input} value={current} onChangeText={setCurrent} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete="current-password" editable={!busy} />
          <Text style={styles.label}>New password</Text>
          <TextInput accessibilityLabel="New password" style={styles.input} value={next} onChangeText={setNext} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete="new-password" maxLength={128} editable={!busy} />
          <Text style={styles.label}>Confirm new password</Text>
          <TextInput accessibilityLabel="Confirm new password" style={styles.input} value={confirmation} onChangeText={setConfirmation} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete="new-password" maxLength={128} editable={!busy} onSubmitEditing={changePassword} />
          {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
          <Pressable disabled={busy} style={[styles.button, busy && { opacity: 0.6 }]} onPress={changePassword}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Change password</Text>}
          </Pressable>
          <Text style={styles.body}>Forgot your current password? Ask your campus administrator to reset it after verifying your identity.</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#FFFDF8' }, content: { padding: 24, gap: 12 },
  title: { fontSize: 28, fontWeight: '800', color: '#151515', marginTop: 16 },
  body: { fontSize: 14, lineHeight: 21, color: '#666' }, label: { fontWeight: '700', marginTop: 8 },
  input: { borderWidth: 1, borderColor: '#CCC', borderRadius: 12, padding: 15, fontSize: 16, color: '#151515', backgroundColor: '#fff' },
  link: { color: '#E63946', fontWeight: '700', paddingVertical: 10 },
  button: { backgroundColor: '#E63946', padding: 17, borderRadius: 12, alignItems: 'center', marginVertical: 12 },
  buttonText: { color: '#fff', fontWeight: '800' }, error: { color: '#B42318', lineHeight: 20 },
});
