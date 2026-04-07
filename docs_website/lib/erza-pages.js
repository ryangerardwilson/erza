import { readFileSync } from "node:fs";
import { join } from "node:path";

const EXAMPLES_ROOT = join(process.cwd(), "..", "app", "examples", "docs");

const pageDefinitions = [
  {
    href: "/",
    label: "Start Here",
    summary: "Install, first run, first file, and the path through the docs.",
    localPath: "app/examples/docs",
    filePath: join(EXAMPLES_ROOT, "index.erza")
  },
  {
    href: "/install",
    label: "Install",
    summary: "Install or upgrade the CLI and verify the launcher.",
    localPath: "app/examples/docs/install",
    filePath: join(EXAMPLES_ROOT, "install", "index.erza")
  },
  {
    href: "/first-run",
    label: "First Run",
    summary: "Open the hosted docs and one local example.",
    localPath: "app/examples/docs/first-run",
    filePath: join(EXAMPLES_ROOT, "first-run", "index.erza")
  },
  {
    href: "/first-file",
    label: "First File",
    summary: "Write the smallest useful .erza page.",
    localPath: "app/examples/docs/first-file",
    filePath: join(EXAMPLES_ROOT, "first-file", "index.erza")
  },
  {
    href: "/components",
    label: "Components",
    summary: "Current primitives, nesting rules, and motion.",
    localPath: "app/examples/docs/components",
    filePath: join(EXAMPLES_ROOT, "components", "index.erza")
  },
  {
    href: "/backend",
    label: "Backend",
    summary: "How backend.py, handlers, and template calls fit together.",
    localPath: "app/examples/docs/backend",
    filePath: join(EXAMPLES_ROOT, "backend", "index.erza")
  },
  {
    href: "/remote",
    label: "Remote",
    summary: "How erza asks a host for terminal pages over HTTPS.",
    localPath: "app/examples/docs/remote",
    filePath: join(EXAMPLES_ROOT, "remote", "index.erza")
  },
  {
    href: "/examples",
    label: "Examples",
    summary: "Local example apps and what each one is for.",
    localPath: "app/examples/docs/examples",
    filePath: join(EXAMPLES_ROOT, "examples", "index.erza")
  },
  {
    href: "/reference",
    label: "Reference",
    summary: "Patterns, labs, and protocol notes after the basics.",
    localPath: "app/examples/docs/reference",
    filePath: join(EXAMPLES_ROOT, "reference", "index.erza")
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
