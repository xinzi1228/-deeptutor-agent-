"use client";

import { LockKeyhole } from "lucide-react";
import { useState } from "react";
import { useLearningProfile } from "./LearningProfileContext";
import { ProfileUnlockDialog } from "./ProfileUnlockDialog";

export function ProfileLockBanner({ children }: { children: React.ReactNode }) {
  const { loading, profiles, active } = useLearningProfile(); const [creating, setCreating] = useState(false); if (loading || active) return <>{children}</>;
  return <div className="relative h-full overflow-hidden"><div className="pointer-events-none h-full select-none blur-[2px] opacity-25">{children}</div><div className="absolute inset-0 flex items-center justify-center bg-[var(--background)]/78 px-5 backdrop-blur-sm"><div className="max-w-md rounded-3xl border border-[var(--border)] bg-[var(--card)] p-8 text-center shadow-xl"><span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--primary)]/10 text-[var(--primary)]"><LockKeyhole size={25} /></span><h1 className="mt-5 text-xl font-semibold text-[var(--foreground)]">先选择学习档案</h1><p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">学习档案会把每个人的对话、记忆、练习和报告分开保存。请从左侧选择并输入 PIN。</p>{profiles.length === 0 && <button onClick={() => setCreating(true)} className="mt-5 rounded-xl bg-[var(--primary)] px-5 py-2.5 font-medium text-[var(--primary-foreground)]">创建第一个学习档案</button>}</div></div>{creating && <ProfileUnlockDialog createMode onClose={() => setCreating(false)} />}</div>;
}
