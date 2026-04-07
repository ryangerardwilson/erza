import { readFileSync } from "node:fs";
import { join } from "node:path";

const EXAMPLES_ROOT = join(process.cwd(), "..", "app", "examples", "docs");

const pageDefinitions = [
  {
    href: "/",
    label: "Docs",
    summary: "Overview, links, and the shared host model.",
    localPath: "app/examples/docs",
    filePath: join(EXAMPLES_ROOT, "index.erza")
  },
  {
    href: "/components",
    label: "Components",
    summary: "Current primitives, nesting rules, and motion.",
    localPath: "app/examples/docs/components",
    filePath: join(EXAMPLES_ROOT, "components", "index.erza")
  },
  {
    href: "/patterns",
    label: "Patterns",
    summary: "Reference screen shapes for the runtime.",
    localPath: "app/examples/docs/patterns",
    filePath: join(EXAMPLES_ROOT, "patterns", "index.erza")
  },
  {
    href: "/labs",
    label: "Labs",
    summary: "Current capability gaps and motion fallback notes.",
    localPath: "app/examples/docs/labs",
    filePath: join(EXAMPLES_ROOT, "labs", "index.erza")
  },
  {
    href: "/protocol",
    label: "Protocol",
    summary: "The minimal HTTPS transport sketch for erzanet.",
    localPath: "app/examples/docs/protocol",
    filePath: join(EXAMPLES_ROOT, "protocol", "index.erza")
  }
];

const pageFiles = new Map(pageDefinitions.map((page) => [page.href, page.filePath]));

export function normalizeErzaPagePath(value = "/") {
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

export function remoteCommandForPage(href) {
  const normalized = normalizeErzaPagePath(href);
  if (!normalized) {
    return null;
  }
  if (normalized === "/") {
    return "erza run erza.ryangerardwilson.com";
  }
  return `erza run erza.ryangerardwilson.com${normalized}`;
}

export function getErzaPageSource(href) {
  const normalized = normalizeErzaPagePath(href);
  if (!normalized) {
    return null;
  }

  const filePath = pageFiles.get(normalized);
  if (!filePath) {
    return null;
  }
  return readFileSync(filePath, "utf8");
}

export const erzaDocsPages = pageDefinitions.map((page) => ({
  href: page.href,
  label: page.label,
  summary: page.summary,
  localPath: page.localPath,
  remoteCommand: remoteCommandForPage(page.href)
}));
