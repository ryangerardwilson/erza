import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import { unified } from "unified";

const REPO_URL = "https://github.com/ryangerardwilson/erza";
const ROOT_SECTION_TITLE = "Overview";

function resolveDocPath(filename) {
  const candidates = [join(process.cwd(), filename), join(process.cwd(), "..", filename)];
  return candidates.find((candidate) => existsSync(candidate)) || candidates[0];
}

const README_PATH = resolveDocPath("README.md");
const SKILLS_PATH = resolveDocPath("SKILLS.md");

const README_PATH_ALIASES = {
  "/": "/",
  "/install": "/install",
  "/first-run": "/quick-start",
  "/first-file": "/a-minimal-app",
  "/remote": "/local-and-remote-model",
  "/components": "/language-surface",
  "/controls": "/runtime-controls",
  "/next": "/where-to-go-next",
  "/reference": "/repo-layout",
  "/development": "/development",
  "/status": "/status"
};

const SKILLS_PATH_ALIASES = {
  "/": "/",
  "/rules": "/build-rules",
  "/actions": "/action-contract",
  "/protocol": "/remote-protocol",
  "/build": "/start-building",
  "/components": "/component-reference",
  "/commands": "/commands",
  "/mistakes": "/common-mistakes",
  "/reference": "/repo-map",
  "/development": "/development",
  "/status": "/current-status"
};

const DOC_CONFIG = {
  readme: {
    filePath: README_PATH,
    mountPath: "/",
    pathAliases: README_PATH_ALIASES,
    screenTitleFallback: "erza"
  },
  skills: {
    filePath: SKILLS_PATH,
    mountPath: "/skills",
    pathAliases: SKILLS_PATH_ALIASES,
    screenTitleFallback: "erza skills"
  }
};

export function readCanonicalReadme() {
  return readFileSync(README_PATH, "utf8");
}

export function readCanonicalSkills() {
  return readFileSync(SKILLS_PATH, "utf8");
}

export function resolveReadmeHref(href = "") {
  if (!href || href.startsWith("#") || href.startsWith("http://") || href.startsWith("https://")) {
    return href;
  }
  const cleaned = href.replace(/^\.\//, "");
  const mode = cleaned.endsWith("/") ? "tree" : "blob";
  return `${REPO_URL}/${mode}/main/${cleaned}`;
}

export function normalizeDocsErzaPath(value = "/") {
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

export const normalizeReadmeErzaPath = normalizeDocsErzaPath;

export function buildDocsErzaSource(requestedPath = "/") {
  const normalized = normalizeDocsErzaPath(requestedPath);
  if (!normalized) {
    return null;
  }

  const { config, docPath } = resolveDocRequest(normalized);
  const sections = parseMarkdownSections(readFileSync(config.filePath, "utf8"), config.screenTitleFallback);
  const aliasResolved = config.pathAliases[docPath] || docPath;
  const selectedPath = sections.some((section) => section.path === aliasResolved)
    ? aliasResolved
    : docPath === "/"
      ? "/"
      : null;
  if (selectedPath === null) {
    return null;
  }

  const lines = [`<Screen title="${escapeAttribute(sections[0]?.screenTitle || config.screenTitleFallback)}">`];
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

export const buildReadmeErzaSource = buildDocsErzaSource;

function resolveDocRequest(normalizedPath) {
  if (normalizedPath === DOC_CONFIG.skills.mountPath || normalizedPath.startsWith(`${DOC_CONFIG.skills.mountPath}/`)) {
    const suffix = normalizedPath.slice(DOC_CONFIG.skills.mountPath.length);
    return {
      config: DOC_CONFIG.skills,
      docPath: suffix ? (suffix.startsWith("/") ? suffix : `/${suffix}`) : "/"
    };
  }
  return {
    config: DOC_CONFIG.readme,
    docPath: normalizedPath
  };
}

function parseMarkdownSections(markdown, screenTitleFallback) {
  const tree = unified().use(remarkParse).use(remarkGfm).parse(markdown);
  const sections = [];
  let screenTitle = screenTitleFallback;
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
