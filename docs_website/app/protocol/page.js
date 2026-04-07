import TerminalBridgePage from "@/ui/terminal-bridge-page";
import { remoteCommandForPage } from "@/lib/erza-pages";

export const metadata = {
  title: "Protocol",
  description: "Terminal-first remote notes for erza."
};

export default function ProtocolPage() {
  return (
    <TerminalBridgePage
      eyebrow="protocol"
      title="The remote model is documented in the terminal version."
      description="The browser page should only point you at the idea. The terminal page carries the request flow, the guardrails, and the current shape of erzanet over HTTPS."
      command={remoteCommandForPage("/protocol")}
      points={[
        "How erza asks a host for terminal-native pages instead of browser documents.",
        "Why the transport should stay declarative and not ship arbitrary backend code to the client."
      ]}
    />
  );
}
