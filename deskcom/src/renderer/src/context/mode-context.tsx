import React, { createContext, useContext } from 'react';
import { getPlatform } from '@/platforms';

export type ModeType = 'pet';

interface ModeContextType {
  mode: ModeType;
  isElectron: boolean;
}

const ModeContext = createContext<ModeContextType | undefined>(undefined);

export const ModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isElectron = getPlatform().name === 'electron';

  return (
    <ModeContext.Provider value={{ mode: 'pet', isElectron }}>
      {children}
    </ModeContext.Provider>
  );
};

export const useMode = (): ModeContextType => {
  const context = useContext(ModeContext);
  if (context === undefined) {
    throw new Error('useMode must be used within a ModeProvider');
  }
  return context;
}; 
