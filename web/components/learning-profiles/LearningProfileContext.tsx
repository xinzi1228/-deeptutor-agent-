"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createLearningProfile, getActiveLearningProfile, listLearningProfiles, lockLearningProfile, unlockLearningProfile, type LearningProfile } from "@/lib/learning-profiles-api";

type Value = { loading: boolean; profiles: LearningProfile[]; active: LearningProfile | null; readOnly: boolean; refresh: () => Promise<void>; create: (name: string, pin: string) => Promise<LearningProfile>; unlock: (profileId: string, pin: string) => Promise<void>; lock: () => Promise<void> };
const Context = createContext<Value | null>(null);

export function useLearningProfile(): Value { const value = useContext(Context); if (!value) throw new Error("useLearningProfile must be used inside LearningProfileProvider"); return value; }

export function LearningProfileProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true); const [profiles, setProfiles] = useState<LearningProfile[]>([]); const [active, setActive] = useState<LearningProfile | null>(null); const [readOnly, setReadOnly] = useState(false);
  const refresh = useCallback(async () => { try { const [listed, current] = await Promise.all([listLearningProfiles(), getActiveLearningProfile()]); setProfiles(listed.profiles); setActive(current.profile); setReadOnly(Boolean(current.read_only)); } finally { setLoading(false); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  const create = useCallback(async (name: string, pin: string) => { const profile = await createLearningProfile({ name, pin }); setProfiles((items) => [...items, profile]); return profile; }, []);
  const unlock = useCallback(async (profileId: string, pin: string) => { const result = await unlockLearningProfile(profileId, pin); setActive(result.profile); setReadOnly(false); window.dispatchEvent(new CustomEvent("deeptutor:learning-profile-changed", { detail: { profileId } })); }, []);
  const lock = useCallback(async () => { await lockLearningProfile(); setActive(null); setReadOnly(false); window.dispatchEvent(new CustomEvent("deeptutor:learning-profile-changed", { detail: { profileId: null } })); }, []);
  const value = useMemo(() => ({ loading, profiles, active, readOnly, refresh, create, unlock, lock }), [loading, profiles, active, readOnly, refresh, create, unlock, lock]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
