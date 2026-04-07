import TerminalBridgePage from "@/ui/terminal-bridge-page";
import { remoteCommandForPage } from "@/lib/erza-pages";

export const metadata = {
  title: "Labs",
  description: "Terminal-first capability notes for erza."
};

export default function LabsPage() {
  return (
    <TerminalBridgePage
      eyebrow="labs"
      title="Capability tracking belongs in the terminal docs."
      description="The browser site only points at the work. The terminal page carries the capability matrix, the animation fallback note, and the gaps between runtime, browser output, and erzanet."
      command={remoteCommandForPage("/labs")}
      points={[
        "What works in the runtime, the browser docs, the remote viewer, and future erzanet transport.",
        "Where AsciiAnimation still falls back to posters and where remote interaction is still read-only."
      ]}
    />
  );
}
