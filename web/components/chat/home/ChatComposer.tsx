"use client";

import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import {
  ArrowUp,
  BookOpen,
  Bot,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Loader2,
  MessageSquare,
  Mic,
  Paperclip,
  Sparkles,
  Square,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  ATTACHMENT_ACCEPT,
  docIconFor,
  formatBytes,
  isSvgFilename,
} from "@/lib/doc-attachments";
import { useTranslation } from "react-i18next";
import type { SelectedHistorySession } from "@/components/chat/HistorySessionPicker";
import type { SelectedQuestionEntry } from "@/components/chat/QuestionBankPicker";
import type { SelectedRecord } from "@/lib/notebook-selection-types";
import type { LLMSelection } from "@/lib/unified-ws";
import type { LLMOption } from "@/lib/llm-options";
import type { SpaceMemoryFile } from "@/lib/space-items";
import type { SelectedBookReference } from "@/lib/book-references";
import KnowledgeSelector from "./KnowledgeSelector";
import ModelSelector from "./ModelSelector";
import PersonaSelector from "./PersonaSelector";

import ContextReferenceTree, {
  type ContextTreeItem,
} from "./ContextReferenceTree";
import { ComposerInput, type ComposerInputHandle } from "./ComposerInput";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";

interface PendingAttachment {
  type: string;
  filename: string;
  base64?: string;
  previewUrl?: string;
  size?: number;
  mimeType?: string;
}

interface KnowledgeBase {
  name: string;
}

interface CapabilityDef {
  value: string;
  label: string;
  description: string;
  icon: LucideIcon;
  allowedTools: string[];
  // Loop-engine capabilities (solve / mastery) run on the chat agent loop and
  // are collapsed into the "More" flyout instead of listed directly.
  loopEngine?: boolean;
}

/** One row in the capability picker — shared by the built-in list and the
 *  "More" flyout so both render identically. */
function CapMenuItem({
  cap,
  selected,
  onSelect,
}: {
  cap: CapabilityDef;
  selected: boolean;
  onSelect: (value: string) => void;
}) {
  const { t } = useTranslation();
  const Icon = cap.icon;
  return (
    <button
      type="button"
      onClick={() => onSelect(cap.value)}
      className={`flex w-full items-center gap-2.5 px-3 py-1.5 text-left transition-colors active:bg-[var(--muted)]/70 ${
        selected ? "bg-[var(--primary)]/[0.06]" : "hover:bg-[var(--muted)]/45"
      }`}
    >
      <Icon
        size={15}
        strokeWidth={1.7}
        className={`shrink-0 ${selected ? "text-[var(--primary)]" : "text-[var(--muted-foreground)]"}`}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12.5px] font-medium leading-snug text-[var(--foreground)]">
          {t(cap.label)}
        </div>
        <div className="truncate text-[11px] leading-snug text-[var(--muted-foreground)]">
          {t(cap.description)}
        </div>
      </div>
      {selected && (
        <Check
          size={14}
          strokeWidth={2}
          className="shrink-0 text-[var(--primary)]"
        />
      )}
    </button>
  );
}

export default memo(function ChatComposer({
  composerRef,
  capMenuRef,
  capBtnRef,
  dragCounter,
  dragging,
  capMenuOpen,
  hasMessages,
  attachments,
  attachmentError,
  activeCap,
  knowledgeBases,
  connectedAgents = [],
  selectedAgent = null,
  onSelectAgent,
  llmOptions,
  activeLLMDefault,
  llmSelection,
  llmOptionsLoading,
  llmOptionsError,
  selectedNotebookRecords,
  selectedBookReferences,
  selectedHistorySessions,
  selectedAgentSessions,
  selectedQuestionEntries,
  notebookReferenceGroups,
  selectedPersona,
  selectedMemoryFiles,
  selectedKnowledgeBases,
  isStreaming,
  isVisualizeMode,
  capabilities,
  onSetCapMenuOpen,
  onToggleKB,
  onSelectLLM,
  onClearPersona,
  personaSelection,
  onPersonaSelectionChange,
  personaSelectorOpen,
  onPersonaSelectorOpenChange,
  onToggleMemoryFile,
  onSend,
  onRemoveAttachment,
  onPreviewAttachment,
  onRemoveHistory,
  onRemoveAgent,
  onRemoveBookReference,
  onRemoveNotebook,
  onRemoveQuestion,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
  onPaste,
  onAddFiles,
  onSelectCapability,
  onCancelStreaming,
  prefillInputRef,
  inputPlaceholder,
  studentMode = false,
}: {
  composerRef: RefObject<HTMLDivElement | null>;
  capMenuRef: RefObject<HTMLDivElement | null>;
  capBtnRef: RefObject<HTMLButtonElement | null>;
  dragCounter: RefObject<number>;
  dragging: boolean;
  capMenuOpen: boolean;
  hasMessages: boolean;
  attachments: PendingAttachment[];
  attachmentError: string | null;
  activeCap: CapabilityDef;
  knowledgeBases: KnowledgeBase[];
  /** Connected local subagents (Claude Code / Codex) selectable for this turn. */
  connectedAgents?: { name: string; kind?: string }[];
  /** The connected agent selected for this turn, if any (single-select). */
  selectedAgent?: string | null;
  onSelectAgent?: (name: string | null) => void;
  llmOptions: LLMOption[];
  activeLLMDefault: LLMSelection | null;
  llmSelection: LLMSelection | null;
  llmOptionsLoading: boolean;
  llmOptionsError: boolean;
  selectedNotebookRecords: SelectedRecord[];
  selectedBookReferences: SelectedBookReference[];
  selectedHistorySessions: SelectedHistorySession[];
  selectedAgentSessions: SelectedHistorySession[];
  selectedQuestionEntries: SelectedQuestionEntry[];
  notebookReferenceGroups: Array<{
    notebookId: string;
    notebookName: string;
    count: number;
  }>;
  selectedPersona: string | null;
  selectedMemoryFiles: SpaceMemoryFile[];
  selectedKnowledgeBases: string[];
  isStreaming: boolean;
  isVisualizeMode: boolean;
  capabilities: CapabilityDef[];
  onSetCapMenuOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  onToggleKB: (name: string) => void;
  onSelectLLM: (selection: LLMSelection | null) => void;
  onClearPersona: () => void;
  /**
   * Session-persona wiring (main chat only). When `onPersonaSelectionChange`
   * is provided, the toolbar shows a PersonaSelector chip and the composer
   * accepts the `/persona` slash command. The quiz follow-up surface omits
   * these and keeps its per-turn persona picker flow.
   */
  personaSelection?: string;
  onPersonaSelectionChange?: (persona: string) => void;
  personaSelectorOpen?: boolean;
  onPersonaSelectorOpenChange?: (open: boolean) => void;
  onToggleMemoryFile: (file: SpaceMemoryFile) => void;
  onSend: (content: string) => void;
  onRemoveAttachment: (index: number) => void;
  onPreviewAttachment?: (index: number) => void;
  onRemoveHistory: (sessionId: string) => void;
  onRemoveAgent: (sessionId: string) => void;
  onRemoveBookReference: (bookId: string) => void;
  onRemoveNotebook: (notebookId: string) => void;
  onRemoveQuestion: (entryId: number) => void;
  onDragEnter: (event: React.DragEvent) => void;
  onDragLeave: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: React.DragEvent) => void;
  onPaste: (event: React.ClipboardEvent) => void;
  onAddFiles: (files: File[]) => void;
  onSelectCapability: (value: string) => void;
  onCancelStreaming: () => void;
  /**
   * Optional ref the composer writes its ``prefillInput`` function into
   * once mounted, so the message-list side (specifically
   * ``AskUserOptions`` chips) can drop a string into the textarea
   * without owning the composer's imperative handle directly.
   */
  prefillInputRef?: React.MutableRefObject<((text: string) => void) | null>;
  /** Override the composer placeholder (e.g. quiz follow-up). */
  inputPlaceholder?: string;
  /** Keep student chrome focused on input, attachment, voice and send. */
  studentMode?: boolean;
}) {
  const { t } = useTranslation();
  const CapIcon = activeCap.icon;

  const [hasContent, setHasContent] = useState(false);
  const [moreCapsOpen, setMoreCapsOpen] = useState(false);
  const [lastCapMenuOpen, setLastCapMenuOpen] = useState(capMenuOpen);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const inputHandleRef = useRef<ComposerInputHandle>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  if (lastCapMenuOpen !== capMenuOpen) {
    setLastCapMenuOpen(capMenuOpen);
    if (!capMenuOpen) setMoreCapsOpen(false);
  }

  useEffect(() => {
    if (!prefillInputRef) return;
    prefillInputRef.current = (text: string) => {
      inputHandleRef.current?.setValue(text);
    };
    return () => {
      if (prefillInputRef) prefillInputRef.current = null;
    };
  }, [prefillInputRef]);

  // Microphone → speech-to-text. Appends the transcript to whatever is already
  // in the composer so a dictated phrase can be combined with typed text.
  const handleTranscript = useCallback((text: string) => {
    const current = inputHandleRef.current?.getValue() || "";
    const next = current.trim() ? `${current.trimEnd()} ${text}` : text;
    inputHandleRef.current?.setValue(next);
  }, []);
  const recorder = useVoiceRecorder(handleTranscript);

  // Composer-row compaction: when the available width drops below ~620 px
  // (e.g. the Viewer panel is open or the user is on a narrow viewport),
  // the cap chip + Tools/Attach/Space labels collide. We measure the
  // composer itself and flip those labels to icon-only below the
  // threshold. Count-badges stay visible so users still see how many
  // things are selected.
  const [composerCompact, setComposerCompact] = useState(false);
  useEffect(() => {
    const el = composerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    setComposerCompact(el.getBoundingClientRect().width < 620);
    const observer = new ResizeObserver(() => {
      if (composerRef.current) {
        setComposerCompact(
          composerRef.current.getBoundingClientRect().width < 620,
        );
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [composerRef]);

  const handlePickFiles = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const picked = Array.from(event.target.files ?? []);
      if (picked.length) onAddFiles(picked);
      // Reset so picking the same file twice still triggers `change`.
      event.target.value = "";
    },
    [onAddFiles],
  );

  useEffect(() => {
    if (!hasMessages) textareaRef.current?.focus();
  }, [hasMessages]);

  const handleSelectCapability = useCallback(
    (value: string) => {
      setMoreCapsOpen(false);
      onSelectCapability(value);
    },
    [onSelectCapability],
  );

  // Functional-update form keeps `handleInputChange` identity stable across
  // every keystroke (no `hasContent` in deps), so the memoized ComposerInput
  // doesn't get re-rendered just because we observed a content-empty toggle.
  const handleInputChange = useCallback((val: string) => {
    const next = !!val.trim();
    setHasContent((prev) => (prev === next ? prev : next));
  }, []);

  const doSend = useCallback(
    (content: string) => {
      onSend(content);
      setHasContent(false);
      inputHandleRef.current?.clear();
    },
    [onSend],
  );

  const hasReferences =
    !!attachments.length ||
    !!selectedBookReferences.length ||
    !!selectedNotebookRecords.length ||
    !!selectedHistorySessions.length ||
    !!selectedAgentSessions.length ||
    !!selectedQuestionEntries.length ||
    !!selectedPersona ||
    !!selectedMemoryFiles.length;

  const canSend = (hasContent || hasReferences) && !isStreaming;

  // Unified reference tree above the textarea: Space references, persona
  // and memory render as quiet monochrome rows, collapsed behind a count
  // by default. File attachments intentionally stay OUT of the tree —
  // they keep their preview cards below the textarea.
  // Knowledge bases are intentionally NOT in this tree: they are a
  // session-level retrieval SCOPE (sticky, persisted), not a one-shot
  // reference like the rows below. That sticky state lives in the
  // toolbar KnowledgeSelector chip instead — same lifecycle class as
  // the persona selector.
  const contextTreeItems: ContextTreeItem[] = [
    ...selectedBookReferences.map(
      (book): ContextTreeItem => ({
        key: `book-${book.bookId}`,
        icon: BookOpen,
        kind: t("Book"),
        label: `${book.bookTitle} (${book.pages.length})`,
        onRemove: () => onRemoveBookReference(book.bookId),
      }),
    ),
    ...notebookReferenceGroups.map(
      (group): ContextTreeItem => ({
        key: `nb-${group.notebookId}`,
        icon: BookOpen,
        kind: t("Notebook"),
        label: `${group.notebookName} (${group.count})`,
        onRemove: () => onRemoveNotebook(group.notebookId),
      }),
    ),
    ...selectedHistorySessions.map(
      (session): ContextTreeItem => ({
        key: `hist-${session.sessionId}`,
        icon: MessageSquare,
        kind: t("Chat History"),
        label: session.title,
        onRemove: () => onRemoveHistory(session.sessionId),
      }),
    ),
    ...selectedAgentSessions.map(
      (session): ContextTreeItem => ({
        key: `agent-${session.sessionId}`,
        icon: Bot,
        kind: t("My Agents"),
        label: session.title,
        onRemove: () => onRemoveAgent(session.sessionId),
      }),
    ),
    ...selectedQuestionEntries.map(
      (entry): ContextTreeItem => ({
        key: `q-${entry.id}`,
        icon: ClipboardList,
        kind: t("Question Bank"),
        label: entry.question,
        onRemove: () => onRemoveQuestion(entry.id),
      }),
    ),
    ...(selectedPersona
      ? [
          {
            key: "persona",
            icon: UserRound,
            kind: t("Persona"),
            label: selectedPersona,
            onRemove: onClearPersona,
          } satisfies ContextTreeItem,
        ]
      : []),
    ...selectedMemoryFiles.map(
      (file): ContextTreeItem => ({
        key: `mem-${file}`,
        icon: Brain,
        kind: t("Memory"),
        label: file === "summary" ? t("Summary") : t("Profile"),
        onRemove: () => onToggleMemoryFile(file),
      }),
    ),
  ];

  const handleManualSend = useCallback(() => {
    if (!canSend) return;
    const content = inputHandleRef.current?.getValue() || "";
    doSend(content);
  }, [canSend, doSend]);

  return (
    <div
      ref={composerRef}
      className={`relative z-20 mx-auto w-full shrink-0 px-6 pb-5 ${hasMessages ? "pt-1 max-w-[960px]" : "max-w-[768px]"}`}
      style={{
        transition: "max-width 650ms cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {hasMessages && (
        <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-transparent to-[var(--background)]/72" />
      )}

      <div className="relative">
        <div
          className={`relative rounded-[26px] border bg-[var(--card)] shadow-[0_1px_2px_rgba(0,0,0,0.025),0_10px_28px_-10px_rgba(0,0,0,0.08)] transition-colors ${
            dragging
              ? "border-[var(--primary)] bg-[var(--primary)]/[0.03]"
              : "border-[var(--border)]/55"
          }`}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          data-drag-counter={dragCounter.current}
        >
          {dragging && (
            <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-[26px] border-2 border-dashed border-[var(--primary)]/50 bg-[var(--primary)]/[0.04]">
              <div className="flex flex-col items-center gap-1 text-[var(--primary)]">
                <Paperclip size={22} strokeWidth={1.6} />
                <span className="text-[13px] font-medium">
                  {t("Drop files here")}
                </span>
                <span className="text-[11px] text-[var(--primary)]/70">
                  {t("Images, Office docs, code & text")}
                </span>
              </div>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ATTACHMENT_ACCEPT}
            onChange={handleFileInputChange}
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
          />

          {contextTreeItems.length > 0 && (
            // The reference zone reads as its own layer: a faint muted band
            // with a hairline against the input area, following the card's
            // top radius.
            <div className="rounded-t-[26px] border-b border-[var(--border)]/30 bg-[var(--muted)]/30 px-4 pb-2 pt-2.5">
              {/* Narrower than the composer on purpose — long titles
                  truncate early so the tree reads as an annotation, not a
                  content row. */}
              <div className="max-w-[min(560px,85%)]">
                <ContextReferenceTree
                  items={contextTreeItems}
                  direction="up"
                  summaryNoun={t("references")}
                />
              </div>
            </div>
          )}
          <ComposerInput
            ref={inputHandleRef}
            textareaRef={textareaRef}
            isVisualizeMode={isVisualizeMode}
            isStreaming={isStreaming}
            canSendEmpty={hasReferences}
            onSend={doSend}
            onInputChange={handleInputChange}
            onPaste={onPaste}
            connectedAgents={studentMode ? [] : connectedAgents}
            selectedAgent={studentMode ? null : selectedAgent}
            onSelectAgent={studentMode ? undefined : onSelectAgent}
            onOpenPersonaSelector={
              onPersonaSelectionChange && onPersonaSelectorOpenChange
                ? () => onPersonaSelectorOpenChange(true)
                : undefined
            }
            placeholder={inputPlaceholder}
            minHeight={hasMessages ? 28 : 64}
          />

          {!!attachments.length && (
            <div className="flex flex-wrap gap-2 px-4 pb-2">
              {attachments.map((a, i) => {
                const previewLabel = t("Preview");
                const removeLabel = t("Remove attachment");
                if (
                  (a.type === "image" || isSvgFilename(a.filename)) &&
                  a.previewUrl
                ) {
                  return (
                    <div
                      key={`${a.filename}-${i}`}
                      className="group relative"
                      title={a.filename || previewLabel}
                    >
                      <button
                        type="button"
                        onClick={() => onPreviewAttachment?.(i)}
                        aria-label={previewLabel}
                        className="relative block h-16 w-16 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]/40"
                      >
                        {/* Native <img> is safe for SVG: scripts inside an
                            SVG don't execute under <img> context. Next.js
                            <Image> rejects SVG by default. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={a.previewUrl}
                          alt={a.filename || t("Attachment preview")}
                          className={`h-full w-full ${isSvgFilename(a.filename) ? "object-contain p-1" : "object-cover"}`}
                        />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveAttachment(i);
                        }}
                        aria-label={removeLabel}
                        className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--foreground)] text-[var(--background)] opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  );
                }
                const spec = docIconFor(a.filename);
                const Icon = spec.Icon;
                const sizeLabel = a.size ? formatBytes(a.size) : "";
                return (
                  <div
                    key={`${a.filename}-${i}`}
                    className="group relative"
                    title={a.filename}
                  >
                    <button
                      type="button"
                      onClick={() => onPreviewAttachment?.(i)}
                      aria-label={previewLabel}
                      className="flex h-16 w-[160px] items-center gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2.5 text-left transition-colors hover:border-[var(--primary)]/40 hover:bg-[var(--muted)]/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]/40"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-[var(--muted)]/60">
                        <Icon
                          size={22}
                          strokeWidth={1.5}
                          className={spec.tint}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[12px] font-medium text-[var(--foreground)]">
                          {a.filename}
                        </div>
                        <div className="truncate text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                          {sizeLabel
                            ? `${spec.label} · ${sizeLabel}`
                            : spec.label}
                        </div>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveAttachment(i);
                      }}
                      aria-label={removeLabel}
                      className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--foreground)] text-[var(--background)] opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
                    >
                      <X size={10} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {attachmentError && (
            <div className="px-4 pb-2 text-[11px] text-red-600">
              {attachmentError}
            </div>
          )}

          {/* Claude-style chrome-free toolbar: no divider against the input
              area, no pill borders — quiet text/icon buttons that surface
              on hover. */}
          <div className="px-3 pb-2 pt-0.5">
            <div className="flex items-center gap-1">
              {!studentMode && (
                <div className="relative">
                <button
                  ref={capBtnRef}
                  onClick={() => onSetCapMenuOpen((v) => !v)}
                  className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2 text-[14px] font-medium transition-[background-color,color,transform] duration-150 active:scale-[0.97] ${
                    capMenuOpen
                      ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                      : "text-[var(--foreground)] hover:bg-[var(--muted)]/55"
                  }`}
                >
                  <span className="flex min-w-0 items-center gap-1.5">
                    <CapIcon size={16} strokeWidth={1.7} className="shrink-0" />
                    {composerCompact ? null : (
                      <span className="truncate">{t(activeCap.label)}</span>
                    )}
                  </span>
                  <ChevronDown
                    size={13}
                    strokeWidth={2}
                    className={`-mr-0.5 shrink-0 transition-transform duration-200 ${capMenuOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {capMenuOpen && (
                  <div
                    ref={capMenuRef}
                    className="dt-popup-up absolute bottom-full left-0 z-50 mb-1.5 w-[260px] overflow-visible rounded-xl border border-[var(--border)] bg-[var(--popover)] py-1 shadow-lg backdrop-blur-md"
                  >
                    {capabilities
                      .filter((cap) => !cap.loopEngine)
                      .map((cap) => (
                        <CapMenuItem
                          key={cap.value}
                          cap={cap}
                          selected={activeCap.value === cap.value}
                          onSelect={handleSelectCapability}
                        />
                      ))}
                    {(() => {
                      const loopCaps = capabilities.filter(
                        (cap) => cap.loopEngine,
                      );
                      if (loopCaps.length === 0) return null;
                      const loopSelected = loopCaps.some(
                        (cap) => cap.value === activeCap.value,
                      );
                      return (
                        <div
                          className="group/more relative"
                          onMouseEnter={() => setMoreCapsOpen(true)}
                          onMouseLeave={() => setMoreCapsOpen(false)}
                          onFocus={() => setMoreCapsOpen(true)}
                          onBlur={(event) => {
                            const next = event.relatedTarget;
                            if (
                              !next ||
                              !event.currentTarget.contains(next as Node)
                            ) {
                              setMoreCapsOpen(false);
                            }
                          }}
                        >
                          <button
                            type="button"
                            aria-haspopup="menu"
                            aria-expanded={moreCapsOpen}
                            onClick={() => setMoreCapsOpen((open) => !open)}
                            className={`flex w-full items-center gap-2.5 px-3 py-1.5 text-left transition-colors ${
                              moreCapsOpen
                                ? "bg-[var(--muted)]/45"
                                : "group-hover/more:bg-[var(--muted)]/45"
                            } ${
                              loopSelected && !moreCapsOpen
                                ? "bg-[var(--primary)]/[0.06]"
                                : ""
                            }`}
                          >
                            <Sparkles
                              size={15}
                              strokeWidth={1.7}
                              className={`shrink-0 ${loopSelected ? "text-[var(--primary)]" : "text-[var(--muted-foreground)]"}`}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[12.5px] font-medium leading-snug text-[var(--foreground)]">
                                {t("More Capabilities")}
                              </div>
                              <div className="truncate text-[11px] leading-snug text-[var(--muted-foreground)]">
                                {t("Agent-loop driven modes")}
                              </div>
                            </div>
                            <ChevronRight
                              size={14}
                              strokeWidth={2}
                              className="shrink-0 text-[var(--muted-foreground)]"
                            />
                          </button>
                          {/* Right flyout. ``pl-1.5`` is a pointer bridge so the
                              cursor can cross the gap without dropping hover;
                              click/focus also open it for touch and keyboard. */}
                          <div
                            className={`absolute bottom-0 left-full z-50 pl-1.5 transition-opacity duration-150 ${
                              moreCapsOpen
                                ? "visible opacity-100"
                                : "invisible opacity-0"
                            }`}
                          >
                            <div className="w-[240px] overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--popover)] py-1 shadow-lg backdrop-blur-md">
                              {loopCaps.map((cap) => (
                                <CapMenuItem
                                  key={cap.value}
                                  cap={cap}
                                  selected={activeCap.value === cap.value}
                                  onSelect={handleSelectCapability}
                                />
                              ))}
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )}
                </div>
              )}

              <div className="ml-auto flex shrink-0 items-center gap-1.5">
                {!studentMode && knowledgeBases.length > 0 ? (
                  <KnowledgeSelector
                    knowledgeBases={knowledgeBases}
                    selected={selectedKnowledgeBases}
                    onToggle={onToggleKB}
                  />
                ) : null}
                {!studentMode && onPersonaSelectionChange ? (
                  <PersonaSelector
                    value={personaSelection ?? ""}
                    onChange={onPersonaSelectionChange}
                    open={personaSelectorOpen}
                    onOpenChange={onPersonaSelectorOpenChange}
                  />
                ) : null}
                {!studentMode && (
                  <ModelSelector
                    options={llmOptions}
                    activeDefault={activeLLMDefault}
                    value={llmSelection}
                    loading={llmOptionsLoading}
                    error={llmOptionsError}
                    onChange={onSelectLLM}
                  />
                )}

                <button
                  type="button"
                  onClick={handlePickFiles}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] text-[var(--muted-foreground)] transition-[background-color,color,transform] duration-150 hover:bg-[var(--muted)]/55 hover:text-[var(--foreground)] active:scale-90"
                  aria-label={t("Attach files")}
                  title={t("Attach files")}
                >
                  <Paperclip size={16} strokeWidth={1.9} />
                </button>

                <button
                  type="button"
                  onClick={recorder.toggle}
                  disabled={recorder.state === "transcribing" || isStreaming}
                  className={`group relative inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] transition-[background-color,color,transform] duration-150 active:scale-90 disabled:opacity-40 ${
                    recorder.state === "recording"
                      ? "bg-red-500/15 text-red-500"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/55 hover:text-[var(--foreground)]"
                  }`}
                  aria-label={
                    recorder.state === "recording"
                      ? t("Stop recording")
                      : t("Record voice")
                  }
                  title={
                    recorder.error ||
                    (recorder.state === "recording"
                      ? t("Stop recording")
                      : t("Record voice"))
                  }
                >
                  {recorder.state === "recording" && (
                    <span className="pointer-events-none absolute inset-0 rounded-[10px] border border-red-500/40 animate-pulse" />
                  )}
                  {recorder.state === "transcribing" ? (
                    <Loader2
                      size={16}
                      strokeWidth={1.9}
                      className="animate-spin"
                    />
                  ) : (
                    <Mic size={16} strokeWidth={1.9} />
                  )}
                </button>

                {isStreaming ? (
                  <button
                    type="button"
                    onClick={onCancelStreaming}
                    className="group relative ml-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[var(--primary)] text-[var(--primary-foreground)] transition-[background-color,transform] duration-150 hover:bg-[var(--primary)]/90 active:scale-95"
                    aria-label={t("Stop generating")}
                    title={t("Stop generating")}
                  >
                    {/* A faint ring slowly rotates inside while streaming,
                        signalling "still working — click to cancel". Kept
                        circular (inset within the rounded square) so the
                        rotation reads as a spinner, not a tumbling box. */}
                    <span className="pointer-events-none absolute inset-[3px] rounded-full border-[1.5px] border-white/25 border-t-white/85 animate-spin opacity-90 transition-opacity group-hover:opacity-40" />
                    <Square
                      size={10}
                      strokeWidth={2.6}
                      className="relative z-10 fill-current"
                    />
                    <span className="sr-only">{t("Stop generating")}</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleManualSend}
                    disabled={!(hasContent || hasReferences) || isStreaming}
                    aria-disabled={!canSend}
                    className="ml-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[var(--primary)] text-[var(--primary-foreground)] transition-[background-color,transform,opacity] duration-150 active:scale-95 disabled:opacity-25 hover:bg-[var(--primary)]/90"
                    aria-label={t("Send")}
                  >
                    <ArrowUp size={16} strokeWidth={2.5} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});
