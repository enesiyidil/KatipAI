/** Minimal markdown renderer for vault content */
export default function MarkdownView({ content }) {
  const html = parseMarkdown(content);
  return <div className="markdown-preview prose-sm" dangerouslySetInnerHTML={{ __html: html }} />;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function parseMarkdown(md) {
  if (!md) return "";
  let text = md;
  // Strip YAML frontmatter
  text = text.replace(/^---[\s\S]*?---\n*/m, "");
  const lines = text.split("\n");
  const out = [];
  let inList = false;

  for (const line of lines) {
    const t = line.trimEnd();
    if (t.startsWith("## ")) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h2>${escapeHtml(t.slice(3))}</h2>`);
    } else if (t.startsWith("### ")) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h3>${escapeHtml(t.slice(4))}</h3>`);
    } else if (t.startsWith("- ")) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${inlineFormat(escapeHtml(t.slice(2)))}</li>`);
    } else if (t.startsWith("> ")) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<blockquote>${inlineFormat(escapeHtml(t.slice(2)))}</blockquote>`);
    } else if (t === "---") {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push("<hr/>");
    } else if (t.startsWith("# ")) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h2>${escapeHtml(t.slice(2))}</h2>`);
    } else if (t) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<p>${inlineFormat(escapeHtml(t))}</p>`);
    }
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function inlineFormat(s) {
  return s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code class='text-emerald-400/80 bg-zinc-800 px-1 rounded text-xs'>$1</code>")
    .replace(/_(.+?)_/g, "<em>$1</em>");
}
