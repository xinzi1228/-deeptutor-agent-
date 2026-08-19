"use client";

export type AnnotationModeKey = "image" | "text" | "audio" | "video";
export type AnnotationModeValue = AnnotationModeKey | "pro";

const KEY_PREFIX = "deeptutor_last_annotation_task";
const MODE_KEY_PREFIX = "deeptutor_last_annotation_mode";

export function lastTaskKeyFor(profileId: string, modal: AnnotationModeValue): string {
  return profileId ? `${KEY_PREFIX}.${profileId}.${modal}` : `${KEY_PREFIX}.${modal}`;
}

export function readLastTaskFor(profileId: string, modal: AnnotationModeValue): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(lastTaskKeyFor(profileId, modal));
  } catch {
    return null;
  }
}

export function writeLastTaskFor(profileId: string, modal: AnnotationModeValue, taskId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(lastTaskKeyFor(profileId, modal), taskId);
  } catch {
    /* ignore quota/security errors */
  }
}

export function lastModeKeyFor(profileId: string): string {
  return profileId ? `${MODE_KEY_PREFIX}.${profileId}` : MODE_KEY_PREFIX;
}

export function readLastModeFor(profileId: string): AnnotationModeValue | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(lastModeKeyFor(profileId));
    const valid: readonly AnnotationModeValue[] = ["image", "text", "audio", "video", "pro"];
    return valid.includes(raw as AnnotationModeValue) ? (raw as AnnotationModeValue) : null;
  } catch {
    return null;
  }
}

export function writeLastModeFor(profileId: string, mode: AnnotationModeValue): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(lastModeKeyFor(profileId), mode);
  } catch {
    /* ignore */
  }
}
