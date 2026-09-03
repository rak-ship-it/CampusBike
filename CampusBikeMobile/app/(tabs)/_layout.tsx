import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const RED = '#E63946';
const GREY = '#77736D';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,

        tabBarActiveTintColor: RED,
        tabBarInactiveTintColor: GREY,

        tabBarStyle: {
          height: 78,
          paddingTop: 8,
          paddingBottom: 12,
          backgroundColor: '#FFFDF8',
          borderTopColor: '#DDD9D2',
        },

        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '800',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Map',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="map-outline"
              size={size}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="ride"
        options={{
          title: 'My Ride',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="bicycle-outline"
              size={size}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="time-outline"
              size={size}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="help"
        options={{
          title: 'Help',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="help-circle-outline"
              size={size}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="explore"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}