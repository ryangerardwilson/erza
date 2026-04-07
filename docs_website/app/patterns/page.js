import TerminalBridgePage from "@/ui/terminal-bridge-page";
import { remoteCommandForPage } from "@/lib/erza-pages";

export const metadata = {
  title: "Patterns",
  description: "Terminal-first pattern notes for erza."
};

export default function PatternsPage() {
  return (
    <TerminalBridgePage
      eyebrow="patterns"
      title="Pattern notes live primarily in the terminal docs."
      description="The browser site stays intentionally light. Use the terminal page for the 79-column reading flow, the pattern list, and the questions each pattern should answer."
      command={remoteCommandForPage("/patterns")}
      points={[
        "Operator dashboard, docs reader, inbox and inspector, settings, launch pad, and animation lab.",
        "Questions about density, focus, hierarchy, and whether the layout still reads calmly at 79 columns."
      ]}
    />
  );
}
