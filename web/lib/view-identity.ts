"use client";

export type ViewIdentity = "student" | "staff";

const VIEW_IDENTITY_KEY = "deeptutor_view_identity";
const VALID: readonly ViewIdentity[] = ["student", "staff"];

/**
 * 当前界面身份（前端视图层）。
 *
 * - AUTH 关闭时：由 localStorage 决定，默认学生（登录页可选）。
 * - AUTH 开启时：调用方应传入真实角色决定（本模块不读 auth，保持职责单一）。
 *
 * 注意：这只是演示/本地单机的视图身份，不替代后端 deeptutor/services/authorization/policy.py。
 */
export function getViewIdentity(): ViewIdentity {
  if (typeof window === "undefined") return "student";
  const raw = window.localStorage.getItem(VIEW_IDENTITY_KEY);
  return VALID.includes(raw as ViewIdentity) ? (raw as ViewIdentity) : "student";
}

export function setViewIdentity(identity: ViewIdentity): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(VIEW_IDENTITY_KEY, identity);
}

export function isStudentView(identity: ViewIdentity): boolean {
  return identity === "student";
}
