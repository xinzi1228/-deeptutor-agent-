"use client";

export type AnnotationModeKey = "image" | "text" | "audio" | "video";

const KEY_PREFIX = "deeptutor_last_annotation_task";

export function lastTaskKeyFor(profileId: string, modal: AnnotationModeKey): string {
  return profileId ? `${KEY_PREFIX}.${profileId}.${modal}` : `${KEY_PREFIX}.${modal}`;
}

export function readLastTaskFor(profileId: string, modal: AnnotationModeKey): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(lastTaskKeyFor(profileId, modal));
  } catch {
    return null;
  }
}

export function writeLastTaskFor(profileId: string, modal: AnnotationModeKey, taskId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(lastTaskKeyFor(profileId, modal), taskId);
  } catch {
    /* ignore quota/security errors */
  }
}
