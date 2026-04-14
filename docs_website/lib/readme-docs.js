import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import { unified } from "unified";

const README_CANDIDATES = [join(process.cwd(), "README.md"), join(process.cwd(), "..", "README.md")];
const README_PATH = README_CANDIDATES.find((candidate) => existsSync(candidate)) || README_CANDIDATES[0];
const REPO_URL = "https://github.com/ryangerardwilson/erza";
const ROOT_SECTION_TITLE = "Overview";
const PATH_ALIASES = {
  "/": "/",
  "/install": "/install",
  "/first-run": "/quick-start",
  "/first-file": "/a-minimal-app",
  "/components": "/language-surface",
  "/backend": "/backend-model",
  "/remote": "/remote-apps",
  "/examples": "/examples",
  "/reference": "/repo-layout",
  "/patterns": "/current-product-model",
  "/labs": "/current-status",
  "/protocol": "/remote-apps"
};

export function readCanonicalReadme() {
  return readFileSync(README_PATH, "utf8");
}

export function resolveReadmeHref(href = "") {
  if (!href || href.startsWith("#") || href.startsWith("http://") || href.startsWith("https://")) {
    return href;
  }
  const cleaned = href.replace(/^\.\//, "");
  const mode = cleaned.endsWith("/") ? "tree" : "blob";
  return `${REPO_URL}/${mode}/main/${cleaned}`;
}

export function normalizeReadmeErzaPath(value = "/") {
  const trimmed = (value || "/").trim();
  if (!trimmed || trimmed === "/") {
    return "/";
  }
  const pathOnly = trimmed.split("?")[0];
  const segments = pathOnly.split("/").filter(Boolean);
  if (!segments.length) {
    return "/";
  }
  if (segments.some((segment) => segment === "." || segment === "..")) {
    return null;
  }
  return `/${segments.join("/")}`;
}

export function buildReadmeErzaSource(requestedPath = "/") {
  const normalized = normalizeReadmeErzaPath(requestedPath);
  if (!normalized) {
    return null;
  }

  const sections = parseReadmeSections(readCanonicalReadme());
  const aliasResolved = PATH_ALIASES[normalized] || normalized;
  const selectedPath = sections.some((section) => section.path === aliasResolved) ? aliasResolved : normalized === "/" ? "/" : null;
  if (selectedPath === null) {
    return null;
  }

  const lines = [`<Screen title="${escapeAttribute(sections[0]?.screenTitle || "erza")}">`];
  for (const [index, section] of sections.entries()) {
    const attrs = [`title="${escapeAttribute(section.title)}"`, `tab-order="${index}"`];
    if (section.path === selectedPath) {
      attrs.push('default-tab="true"');
    }
    lines.push(`  <Section ${attrs.join(" ")}>`);
    for (const block of section.blocks) {
      if (block.kind === "header") {
        lines.push(`    <Header>${escapeMarkupText(block.text)}</Header>`);
      } else if (block.kind === "text") {
        lines.push(`    <Text>${escapeMarkupText(block.text)}</Text>`);
      } else if (block.kind === "ascii") {
        lines.push("    <AsciiArt>");
        lines.push(indentAscii(block.text, 6));
        lines.push("    </AsciiArt>");
      } else if (block.kind === "link") {
        lines.push(`    <Link href="${escapeAttribute(block.href)}">${escapeMarkupText(block.label)}</Link>`);
      }
    }
    lines.push("  </Section>");
  }
  lines.push("</Screen>");
  return lines.join("\n");
}

function parseReadmeSections(markdown) {
  const tree = unified().use(remarkParse).use(remarkGfm).parse(markdown);
  const sections = [];
  let screenTitle = "erza";
  let current = createSection(ROOT_SECTION_TITLE, "/", screenTitle);

  for (const node of tree.children || []) {
    if (node.type === "heading") {
      const headingText = flattenInline(node.children || []).trim();
      if (!headingText) {
        continue;
      }
      if (node.depth === 1) {
        screenTitle = headingText;
        current.screenTitle = screenTitle;
        current.blocks.push({ kind: "header", text: headingText });
        continue;
      }
      if (node.depth === 2) {
        sections.push(finalizeSection(current, screenTitle));
        current = createSection(headingText, `/${slugify(headingText)}`, screenTitle);
        continue;
      }
      current.blocks.push({ kind: "header", text: headingText });
      continue;
    }

    appendNodeToSection(current, node);
  }

  sections.push(finalizeSection(current, screenTitle));
  return sections;
}

function createSection(title, path, screenTitle) {
  return {
    title,
    path,
    blocks: [],
    screenTitle
  };
}

function finalizeSection(section, screenTitle) {
  const blocks = section.blocks.length
    ? section.blocks
    : [{ kind: "text", text: "No content in this section yet." }];
  return {
    title: section.title,
    path: section.path,
    blocks,
    screenTitle
  };
}

function appendNodeToSection(section, node) {
  if (!node) {
    return;
  }

  if (node.type === "paragraph") {
    const text = flattenInline(node.children || []).trim();
    if (text) {
      section.blocks.push({ kind: "text", text });
    }
    return;
  }

  if (node.type === "list") {
    node.children.forEach((item, index) => {
      const prefix = node.ordered ? `${index + 1}. ` : "- ";
      const text = flattenListItem(item).trim();
      if (text) {
        section.blocks.push({ kind: "text", text: `${prefix}${text}` });
      }
    });
    return;
  }

  if (node.type === "code") {
    const code = String(node.value || "").replace(/\r\n?/g, "\n").trimEnd();
    if (code) {
      section.blocks.push({ kind: "ascii", text: code });
    }
    return;
  }

  if (node.type === "blockquote") {
    const quoted = collectTextFromNodes(node.children || []).trim();
    if (quoted) {
      section.blocks.push({ kind: "text", text: `> ${quoted}` });
    }
    return;
  }

  if (node.type === "thematicBreak") {
    return;
  }

  if (node.type === "table") {
    const rendered = renderTable(node);
    if (rendered) {
      section.blocks.push({ kind: "ascii", text: rendered });
    }
    return;
  }
}

function flattenListItem(node) {
  return collectTextFromNodes(node.children || []);
}

function collectTextFromNodes(nodes) {
  return nodes
    .map((child) => {
      if (child.type === "paragraph") {
        return flattenInline(child.children || []);
      }
      if (child.type === "list") {
        return child.children
          .map((item, index) => {
            const prefix = child.ordered ? `${index + 1}. ` : "- ";
            return `${prefix}${flattenListItem(item)}`;
          })
          .join(" ");
      }
      if (child.type === "code") {
        return String(child.value || "");
      }
      return flattenInline(child.children || []);
    })
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function flattenInline(nodes) {
  return nodes
    .map((node) => {
      if (node.type === "text") {
        return node.value || "";
      }
      if (node.type === "inlineCode") {
        return `\`${node.value || ""}\``;
      }
      if (node.type === "break") {
        return " ";
      }
      if (node.type === "link") {
        const label = flattenInline(node.children || []).trim() || resolveReadmeHref(node.url || "");
        const href = resolveReadmeHref(node.url || "");
        return href ? `${label} (${href})` : label;
      }
      if (node.children) {
        return flattenInline(node.children);
      }
      return "";
    })
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}

function renderTable(node) {
  const rows = (node.children || []).map((row) =>
    (row.children || []).map((cell) => flattenInline(cell.children || []).trim())
  );
  if (!rows.length) {
    return "";
  }
  const columnCount = Math.max(...rows.map((row) => row.length), 0);
  const widths = Array.from({ length: columnCount }, (_, index) =>
    Math.max(...rows.map((row) => (row[index] || "").length), 0)
  );
  const separator = `+${widths.map((width) => "-".repeat(width + 2)).join("+")}+`;
  return rows
    .map((row, index) => {
      const line = `|${widths
        .map((width, cellIndex) => ` ${(row[cellIndex] || "").padEnd(width, " ")} `)
        .join("|")}|`;
      if (index === 0) {
        return [separator, line, separator].join("\n");
      }
      return line;
    })
    .concat(separator)
    .join("\n");
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "section";
}

function escapeMarkupText(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttribute(value) {
  return escapeMarkupText(value).replace(/"/g, "&quot;");
}

function indentAscii(value, spaces) {
  const prefix = " ".repeat(spaces);
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => `${prefix}${escapeMarkupText(line)}`)
    .join("\n");
}
