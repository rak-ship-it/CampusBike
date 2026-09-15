import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { router } from 'expo-router';

export const API_BASE_URL =
  (process.env.EXPO_PUBLIC_API_BASE_URL || '').trim().replace(/\/$/, '');

const TOKEN_KEY = 'campusbike_access_token';
// Web previews deliberately keep tokens in memory, not localStorage.
let webToken: string | null = null;

export async function getToken(): Promise<string | null> {
  return Platform.OS === 'web' ? webToken : SecureStore.getItemAsync(TOKEN_KEY);
}

export async function saveToken(token: string) {
  if (Platform.OS === 'web') webToken = token;
  else await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearSession() {
  if (Platform.OS === 'web') webToken = null;
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
  await AsyncStorage.removeItem('campusbike_student');
}

export async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  else options.signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, timeoutMs);
  try {
    // Never automatically retry writes: a timeout can follow a committed write.
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}

export async function apiFetch(url: string, options: RequestInit = {}) {
  if (!API_BASE_URL) throw new Error('Configure EXPO_PUBLIC_API_BASE_URL before starting Expo.');
  if (!url.startsWith(`${API_BASE_URL}/`)) throw new Error('Invalid API destination.');
  const token = await getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetchWithTimeout(url, { ...options, headers });
  // A delayed failure from an older session must not erase a new login.
  if (response.status === 401 && (await getToken()) === token) {
    await clearSession();
    router.replace('/');
  }
  return response;
}

export async function logoutSession() {
  const response = await apiFetch(`${API_BASE_URL}/api/logout`, { method: 'POST' });
  if (!response.ok && response.status !== 401) throw new Error('Could not sign out. Try again.');
  await clearSession();
}
