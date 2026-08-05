import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';
import { LAppAdapter } from '../WebSDK/src/lappadapter';
import { initPlatform } from '@/platforms';
import './i18n';

const originalConsoleWarn = console.warn;
console.warn = (...args) => {
  if (typeof args[0] === 'string' && args[0].includes('onnxruntime')) {
    return;
  }
  originalConsoleWarn.apply(console, args);
};

// Suppress specific console.error messages from @chatscope/chat-ui-kit-react
const originalConsoleError = console.error;
const errorMessagesToIgnore = ["Warning: Failed"];
console.error = (...args: any[]) => {
  if (typeof args[0] === 'string') {
    const shouldIgnore = errorMessagesToIgnore.some(msg => args[0].startsWith(msg));
    if (shouldIgnore) {
      return;
    }
  }
  originalConsoleError.apply(console, args);
};

if (typeof window !== 'undefined') {
  (window as any).getLAppAdapter = () => LAppAdapter.getInstance();
}

// Initialize platform abstraction, then render React
const rootElement = document.getElementById('root');
if (rootElement) {
  initPlatform().then(() => {
    createRoot(rootElement).render(<App />);
  });
}

// Then load Live2D Core asynchronously
const loadLive2DCore = (): Promise<void> => {
  return new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = './libs/live2dcubismcore.js';
    script.onload = () => {
      console.log('Live2D Cubism Core loaded successfully.');
      resolve();
    };
    script.onerror = (error) => {
      console.error('Failed to load Live2D Cubism Core:', error);
      reject(error);
    };
    document.head.appendChild(script);
  });
};

loadLive2DCore()
  .catch((error) => {
    console.error('Live2D Core failed to load:', error);
  });
