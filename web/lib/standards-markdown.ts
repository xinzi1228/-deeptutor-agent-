/**
 * In-chat standards citations. The annotation coach cites a standard document
 * by writing `〔规范: docId§section〕` (or `〔规范: docId〕`) in its markdown
 * output. A remark plugin turns each marker into a link using the reserved
 * `standard:` scheme, and the renderers' `a` component intercepts it to render
 * a clickable chip that opens the StandardDialog with the doc content.
 *
 * The `standard:` scheme is allow-listed in SAFE_MARKDOWN_PROTOCOL_REGEX
 * (lib/markdown-display.ts) so the href survives markdown URL sanitization —
 * same treatment as the `attachment:` scheme. These links are never emitted as
 * navigable anchors, so allowing the scheme is safe.
 */

export type StandardRef = {
  docId: string;
  section?: string;
};

export const STANDARD_REF_REGEX = /〔规范:\s*([^〕§]+?)(?:§([^〕]+?))?〕/g;

export const STANDARD_HREF_PREFIX = "standard:";

/**
 * True when the content starts a `〔规范: ...〕` marker. Matches the opening
 * token (`〔规范:`) rather than the full marker with its closing `〕`, so
 * detection during streaming is monotonic — once the coach begins a marker the
 * renderer can commit to the rich path without flipping back as more tokens
 * arrive.
 */
export function containsStandardMarker(content: string): boolean {
  return /〔规范\s*:/.test(content);
}

/** Parse the first `〔规范: docId§section〕` marker out of a text string. */
export function parseStandardRef(text: string): StandardRef | null {
  STANDARD_REF_REGEX.lastIndex = 0;
  const match = STANDARD_REF_REGEX.exec(text);
  if (!match) return null;
  const docId = String(match[1] ?? "").trim();
  if (!docId) return null;
  const section = String(match[2] ?? "").trim() || undefined;
  return section ? { docId, section } : { docId };
}

/** Decode a `standard:docId§section` href back into a StandardRef. */
export function parseStandardHref(
  href?: string,
): StandardRef | null {
  if (!href || !href.startsWith(STANDARD_HREF_PREFIX)) return null;
  let raw = href.slice(STANDARD_HREF_PREFIX.length);
  // Markdown URL-sanitization percent-encodes `§` and CJK — decode before
  // splitting so docId/section come back readable and match the dialog lookup.
  try {
    raw = decodeURIComponent(raw);
  } catch {
    // leave raw as-is if it isn't valid percent-encoding
  }
  const sep = raw.indexOf("§");
  const docId = (sep >= 0 ? raw.slice(0, sep) : raw).trim();
  if (!docId) return null;
  const section = (sep >= 0 ? raw.slice(sep + 1) : "").trim() || undefined;
  return section ? { docId, section } : { docId };
}

// mdast node types whose text must NOT be rewritten (code, existing links,
// math). Markers inside these are shown verbatim.
const SKIP_NODE_TYPES = new Set([
  "code",
  "inlineCode",
  "link",
  "linkReference",
  "definition",
  "math",
  "inlineMath",
  "html",
]);

function splitText(value: string): Array<Record<string, unknown>> {
  const nodes: Array<Record<string, unknown>> = [];
  STANDARD_REF_REGEX.lastIndex = 0;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = STANDARD_REF_REGEX.exec(value)) !== null) {
    const docId = String(match[1] ?? "").trim();
    const section = String(match[2] ?? "").trim() || undefined;
    if (match.index > lastIndex) {
      nodes.push({ type: "text", value: value.slice(lastIndex, match.index) });
    }
    if (docId) {
      nodes.push({
        type: "link",
        url: `${STANDARD_HREF_PREFIX}${docId}${section ? `§${section}` : ""}`,
        title: null,
        children: [
          {
            type: "text",
            value: `📖 ${docId}${section ? ` §${section}` : ""}`,
          },
        ],
      });
    } else {
      nodes.push({ type: "text", value: match[0] });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < value.length) {
    nodes.push({ type: "text", value: value.slice(lastIndex) });
  }
  return nodes;
}

/**
 * Build a remark plugin that rewrites every `〔规范: docId§section〕` marker in
 * plain text into a `standard:` link. The renderers' `a` component intercepts
 * the scheme and renders a clickable chip instead of a navigable anchor.
 */
export function makeStandardRefRemarkPlugin() {
  const visit = (node: Record<string, unknown>): void => {
    const children = node.children as
      | Array<Record<string, unknown>>
      | undefined;
    if (!Array.isArray(children)) return;
    const out: Array<Record<string, unknown>> = [];
    for (const child of children) {
      if (child.type === "text" && typeof child.value === "string") {
        out.push(...splitText(child.value));
      } else {
        if (!SKIP_NODE_TYPES.has(child.type as string)) visit(child);
        out.push(child);
      }
    }
    node.children = out;
  };

  return () => (tree: Record<string, unknown>) => visit(tree);
}
