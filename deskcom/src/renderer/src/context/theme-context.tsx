import React, { createContext, useContext, useCallback, useEffect } from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';

export type UiTheme = 'default' | 'sketch';

interface ThemeContextType {
  uiTheme: UiTheme;
  setUiTheme: (theme: UiTheme) => void;
}

const UI_THEME_KEY = 'uiTheme';

function applyDataTheme(theme: UiTheme) {
  if (theme === 'sketch') {
    document.documentElement.setAttribute('data-theme', 'sketch');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [uiTheme, setUiTheme] = useLocalStorage<UiTheme>(UI_THEME_KEY, 'default');

  useEffect(() => {
    applyDataTheme(uiTheme);
  }, [uiTheme]);

  const setTheme = useCallback((theme: UiTheme) => {
    setUiTheme(theme);
    applyDataTheme(theme);
  }, [setUiTheme]);

  return (
    <ThemeContext.Provider value={{ uiTheme, setUiTheme: setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
