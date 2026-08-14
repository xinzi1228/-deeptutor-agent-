"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useLearningProfile } from "@/components/learning-profiles/LearningProfileContext";
import { openCurrentLearningTask, type CurrentLearningTask } from "@/lib/current-learning-task-api";
import { ProfileScopedRequest } from "@/lib/profile-scoped-request";
import { getStudentHomeDashboard, invalidateStudentDashboard } from "@/lib/student-dashboard-api";

type Value = {
  task: CurrentLearningTask | null;
  loading: boolean;
  refresh: () => Promise<void>;
  openTask: (input: { courseId: string; taskId: string; mode: CurrentLearningTask["mode"] }) => Promise<void>;
};

const Context = createContext<Value | null>(null);

export function useCurrentLearningTask(): Value {
  const value = useContext(Context);
  if (!value) throw new Error("useCurrentLearningTask must be used inside CurrentLearningTaskProvider");
  return value;
}

export function CurrentLearningTaskProvider({ children }: { children: ReactNode }) {
  const { active } = useLearningProfile();
  const [task, setTask] = useState<CurrentLearningTask | null>(null);
  const [loading, setLoading] = useState(false);
  const scopeRef = useRef(new ProfileScopedRequest());
  const visibleTask = task?.profile_id === active?.id ? task : null;

  const refresh = useCallback(async () => {
    if (!active) return;
    const request = scopeRef.current.begin();
    setLoading(true);
    try {
      const payload = await getStudentHomeDashboard(active.id, request.signal);
      if (scopeRef.current.accepts(request.generation)) setTask(payload.task);
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) throw error;
    } finally {
      if (scopeRef.current.accepts(request.generation)) setLoading(false);
    }
  }, [active]);

  useEffect(() => {
    scopeRef.current.switchProfile();
    if (!active) return;
    const request = scopeRef.current.begin();
    void getStudentHomeDashboard(active.id, request.signal)
      .then((payload) => {
        if (scopeRef.current.accepts(request.generation)) setTask(payload.task);
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) return;
      });
  }, [active]);

  const openTask = useCallback(async (input: { courseId: string; taskId: string; mode: CurrentLearningTask["mode"] }) => {
    if (!active) return;
    const request = scopeRef.current.begin();
    const next = await openCurrentLearningTask(
      { ...input, expectedVersion: visibleTask?.version ?? 0 },
      request.signal,
    );
    if (scopeRef.current.accepts(request.generation) && next.profile_id === active.id) {
      invalidateStudentDashboard(active.id);
      setTask((current) => (!current || next.version >= current.version ? next : current));
    }
  }, [active, visibleTask?.version]);

  const value = useMemo(() => ({ task: visibleTask, loading, refresh, openTask }), [visibleTask, loading, refresh, openTask]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
