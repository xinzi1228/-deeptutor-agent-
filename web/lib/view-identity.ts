"use client";

import { useSyncExternalStore } from "react";

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
  try {
    const raw = window.localStorage.getItem(VIEW_IDENTITY_KEY);
    return VALID.includes(raw as ViewIdentity) ? (raw as ViewIdentity) : "student";
  } catch {
    // localStorage may be disabled (privacy mode / blocked cookies)
    return "student";
  }
}

export function setViewIdentity(identity: ViewIdentity): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(VIEW_IDENTITY_KEY, identity);
  } catch {
    // localStorage may be disabled - silently no-op
  }
}

export function isStudentView(identity: ViewIdentity): boolean {
  return identity === "student";
}

/**
 * 纯函数：解析当前界面身份。
 *
 * - AUTH 开启（authEnabled === true）：由真实角色决定，admin → staff，否则 student。
 * - AUTH 关闭（authEnabled === false / 未传）：回退到 localStorage 存储身份。
 */
export function resolveViewIdentity(options?: {
  authEnabled?: boolean;
  isAdmin?: boolean;
}): ViewIdentity {
  if (options?.authEnabled === true) {
    return options.isAdmin ? "staff" : "student";
  }
  return getViewIdentity();
}

/**
 * 订阅 localStorage 身份变更（storage 事件，AUTH 关闭时的数据源）。
 */
function subscribeViewIdentity(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

/**
 * 返回当前界面身份。AUTH 关闭时由 localStorage 驱动（可响应 storage 变更），
 * AUTH 开启时由调用方传入的 authEnabled/isAdmin 决定。
 */
export function useViewIdentity(options?: {
  authEnabled?: boolean;
  isAdmin?: boolean;
}): { identity: ViewIdentity; studentMode: boolean } {
  const stored = useSyncExternalStore(
    subscribeViewIdentity,
    getViewIdentity,
    (): ViewIdentity => "student",
  );

  const identity =
    options?.authEnabled === true ? resolveViewIdentity(options) : stored;

  return { identity, studentMode: identity === "student" };
}
