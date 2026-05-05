const REPO_URL = "https://github.com/ryangerardwilson/erza";

export function buildLlmsIndex(origin = "https://erza.ryangerardwilson.com") {
  const lines = [
    "# erza",
    "",
    "AI-facing index for erza docs.",
    "",
    "Primary HTML docs:",
    "- README: " + origin + "/",
    "- SKILLS: " + origin + "/skills",
    "- CHAT_SURFACES_SPEC: " + origin + "/chat",
    "- EXAMPLE: " + origin + "/example",
    "",
    "Primary source files:",
    "- README.md: " + REPO_URL + "/blob/main/README.md",
    "- SKILLS.md: " + REPO_URL + "/blob/main/SKILLS.md",
    "- CHAT_SURFACES_SPEC.md: " + REPO_URL + "/blob/main/CHAT_SURFACES_SPEC.md",
    "- koinonia/index.erza: " + REPO_URL + "/blob/main/koinonia/index.erza",
    "",
    "Project summary:",
    "- erza is a terminal-native UI language and runtime.",
    "- SKILLS.md is the main operating guide for AI agents.",
    "- CHAT_SURFACES_SPEC.md defines the reusable chat TUI runtime contract.",
    "- The example page is the live koinonia/index.erza source with inline comments.",
    "",
    "If you are evaluating the project quickly, read in this order:",
    "1. " + origin + "/skills",
    "2. " + origin + "/chat",
    "3. " + origin + "/example",
    "4. " + origin + "/"
  ];
  return lines.join("\n");
}
