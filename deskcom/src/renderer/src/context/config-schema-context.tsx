import { createContext, useContext, useState, useMemo, useCallback, ReactNode } from 'react';

interface ConfigSchemaState {
  schema: any;
  setSchema: (schema: any) => void;
  refreshSchema: () => void;
  onSchemaRefreshed: (cb: () => void) => () => void;
}

const defaultState: ConfigSchemaState = {
  schema: null,
  setSchema: () => {},
  refreshSchema: () => {},
  onSchemaRefreshed: () => () => {},
};

export const ConfigSchemaContext = createContext<ConfigSchemaState>(defaultState);

export function ConfigSchemaProvider({ children }: { children: ReactNode }) {
  const [schema, setSchema] = useState<any>(null);
  const [refreshListeners, setRefreshListeners] = useState<Array<() => void>>([]);

  const refreshSchema = useCallback(() => {
    refreshListeners.forEach((cb) => cb());
  }, [refreshListeners]);

  const onSchemaRefreshed = useCallback((cb: () => void) => {
    setRefreshListeners((prev) => [...prev, cb]);
    return () => setRefreshListeners((prev) => prev.filter((x) => x !== cb));
  }, []);

  const value = useMemo(
    () => ({ schema, setSchema, refreshSchema, onSchemaRefreshed }),
    [schema, refreshSchema, onSchemaRefreshed],
  );

  return (
    <ConfigSchemaContext.Provider value={value}>
      {children}
    </ConfigSchemaContext.Provider>
  );
}

export function useConfigSchema() {
  const context = useContext(ConfigSchemaContext);
  if (!context) {
    throw new Error('useConfigSchema must be used within ConfigSchemaProvider');
  }
  return context;
}
