import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, Notification, Theme } from '@/types';

interface AppState {
  // Auth
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  setAuthenticated: (value: boolean) => void;
  
  // Theme
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  
  // Sidebar
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (value: boolean) => void;
  toggleSidebar: () => void;
  
  // Notifications
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  
  // System metrics
  cpuUsage: number;
  memoryUsage: number;
  setSystemMetrics: (cpu: number, memory: number) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Auth
      user: null,
      isAuthenticated: true, // Default to true for demo
      setUser: (user) => set({ user }),
      setAuthenticated: (value) => set({ isAuthenticated: value }),
      
      // Theme
      theme: 'dark',
      setTheme: (theme) => {
        set({ theme });
        document.documentElement.classList.toggle('dark', theme === 'dark');
      },
      toggleTheme: () => {
        const newTheme = get().theme === 'dark' ? 'light' : 'dark';
        set({ theme: newTheme });
        document.documentElement.classList.toggle('dark', newTheme === 'dark');
      },
      
      // Sidebar
      sidebarCollapsed: false,
      setSidebarCollapsed: (value) => set({ sidebarCollapsed: value }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      
      // Notifications
      notifications: [],
      addNotification: (notification) => {
        const id = Math.random().toString(36).substring(7);
        set((state) => ({
          notifications: [...state.notifications, { ...notification, id }],
        }));
        setTimeout(() => {
          get().removeNotification(id);
        }, notification.duration || 4000);
      },
      removeNotification: (id) => {
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        }));
      },
      clearNotifications: () => set({ notifications: [] }),
      
      // System metrics
      cpuUsage: 0,
      memoryUsage: 0,
      setSystemMetrics: (cpu, memory) => set({ cpuUsage: cpu, memoryUsage: memory }),
    }),
    {
      name: 'forwarder-pro-storage',
      partialize: (state) => ({ theme: state.theme, sidebarCollapsed: state.sidebarCollapsed }),
    }
  )
);

// Mock data store for demo
interface MockDataState {
  stats: {
    todayForwards: number;
    activeRules: number;
    dedupCache: number;
    errorRate: number;
  };
  updateStats: () => void;
}

export const useMockDataStore = create<MockDataState>()((set) => ({
  stats: {
    todayForwards: 15234,
    activeRules: 24,
    dedupCache: 8932,
    errorRate: 0.32,
  },
  updateStats: () => {
    set((state) => ({
      stats: {
        todayForwards: state.stats.todayForwards + Math.floor(Math.random() * 10),
        activeRules: state.stats.activeRules,
        dedupCache: state.stats.dedupCache + Math.floor(Math.random() * 5),
        errorRate: Math.max(0, Math.min(1, state.stats.errorRate + (Math.random() - 0.5) * 0.1)),
      },
    }));
  },
}));
