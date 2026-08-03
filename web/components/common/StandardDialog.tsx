"use client";

import { useEffect, useState } from "react";
import { X, BookOpen } from "lucide-react";
import { getStandards, type StandardDoc } from "@/lib/standards-api";

export function StandardDialog({
  docId,
  section,
  onClose,
}: {
  docId: string;
  section?: string | null;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<StandardDoc | null>(null);
  useEffect(() => {
    let cancelled = false;
    getStandards()
      .then((r) => {
        if (!cancelled)
          setDoc(r.standards.find((d) => d.id === docId) ?? null);
      })
      .catch(() => {
        if (!cancelled) setDoc(null);
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  if (!doc) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-blue-500" />
            <h3 className="text-sm font-bold">
              {doc.title}
              {section ? ` · ${section}` : ""}
            </h3>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>
        <pre className="whitespace-pre-wrap font-mono text-xs leading-5 text-[var(--foreground)]">
          {doc.content}
        </pre>
      </div>
    </div>
  );
}
