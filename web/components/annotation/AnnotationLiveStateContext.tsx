"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type AnnotationLiveState = {
  taskId: string;
  annotationCount: number;
  labels: string[];
  selectedObjectId: string;
  currentLabel: string;
  tool: string;
  missingObjects: string[];
};

type Value = {
  liveState: AnnotationLiveState | null;
  updateLiveState: (state: Partial<AnnotationLiveState>) => void;
};

const Context = createContext<Value>({
  liveState: null,
  updateLiveState: () => {},
});

export function AnnotationLiveStateProvider({ children }: { children: ReactNode }) {
  const [liveState, setLiveState] = useState<AnnotationLiveState | null>(null);
  const updateLiveState = useCallback((state: Partial<AnnotationLiveState>) => {
    setLiveState((current) => ({
      ...(current || {
        taskId: "",
        annotationCount: 0,
        labels: [],
        selectedObjectId: "",
        currentLabel: "",
        tool: "",
        missingObjects: [],
      }),
      ...state,
    }));
  }, []);
  const value = useMemo(() => ({ liveState, updateLiveState }), [liveState, updateLiveState]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAnnotationLiveState(): Value {
  return useContext(Context);
}
