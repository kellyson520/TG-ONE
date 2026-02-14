import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

// Initialize theme
const savedTheme = localStorage.getItem('forwarder-pro-storage');
if (savedTheme) {
  try {
    const { state } = JSON.parse(savedTheme);
    if (state?.theme === 'dark') {
      document.documentElement.classList.add('dark');
    }
  } catch {
    // Ignore parse errors
  }
} else {
  // Default to dark theme
  document.documentElement.classList.add('dark');
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
