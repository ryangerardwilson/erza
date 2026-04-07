const buildStamp = `${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC`;

export const site = {
  domain: "erza.ryangerardwilson.com",
  url: "https://erza.ryangerardwilson.com",
  repoUrl: "https://github.com/ryangerardwilson/erza",
  buildStamp
};

export const nav = [
  { href: "/", label: "Overview" },
  { href: "/components", label: "Components" },
  { href: "/patterns", label: "Patterns" },
  { href: "/labs", label: "Labs" },
  { href: "/protocol", label: "Protocol" },
  { href: site.repoUrl, label: "GitHub", external: true }
];

export const commands = [
  { label: "Landing demo", command: "python -m erza run examples/landing" },
  { label: "Local example", command: "python -m erza run examples/greetings" },
  { label: "Animation lab", command: "python -m erza run examples/animation" },
  { label: "Remote docs", command: "python -m erza run erza.ryangerardwilson.com" },
  { label: "Legacy docs build", command: "./update_docs.sh" }
];

export const storyPhrases = [
  "the internet did not need a web browser or Android/iOS gatekeepers?",
  "websites could open and be navigated directly from the terminal?",
  "frontend was redesigned to be CLI and TUI first?"
];

export const landingCommand = "python -m erza run examples/landing";
export const landingVideo = "/assets/landing-demo.mp4";
export const landingMarkup = `<Screen title="Erzanet">
  <Section title="What If">
    <Text>What if websites opened directly in the terminal?</Text>
    <Text>What if the network felt calmer than the browser?</Text>
  </Section>

  <Section title="Navigate">
    <Link href="/components/">Inspect components</Link>
    <Link href="/labs/">Inspect the capability matrix</Link>
  </Section>

  <Section title="Signal">
    <AsciiAnimation label="Pulse" fps="6">
      <Frame>+---+\n|*  |\n+---+</Frame>
      <Frame>+---+\n| * |\n+---+</Frame>
      <Frame>+---+\n|  *|\n+---+</Frame>
    </AsciiAnimation>
  </Section>
</Screen>`;

export const pillars = [
  {
    title: "Component-first, not browser-first",
    body:
      "The long-term shape is a component system for terminal interfaces, with titled panels as the current house style rather than browser pages re-skinned in a shell."
  },
  {
    title: "The terminal stays in charge",
    body:
      "The runtime owns layout, focus, history, and motion so the user stays in one keyboard-native environment instead of bouncing through browser chrome."
  },
  {
    title: "Erzanet is the next container",
    body:
      "The hosted docs site is a proving ground for a future where remote apps and documents can be opened as `erza example.com` without leaving the terminal."
  }
];

export const componentFamilies = [
  {
    name: "Shell",
    summary: "Top-level structure and page rhythm.",
    items: ['<Screen title="...">', '<Section title="...">', '<Column gap="...">', '<Row gap="...">']
  },
  {
    name: "Content",
    summary: "Readable surfaces and document structure.",
    items: ["<Header>", "<Text>", '<Link href="...">']
  },
  {
    name: "Action",
    summary: "Intentional affordances instead of browser chrome.",
    items: ['<Action on:press="...">', '<Button on:press="...">']
  },
  {
    name: "Motion",
    summary: "Terminal-safe movement without video or canvas baggage.",
    items: ['<AsciiAnimation fps="...">', "<Frame>...</Frame>"]
  }
];

export const nestingRules = [
  {
    parent: "<Screen>",
    allows: "top-level panels, layout containers, and other shell-level components",
    body:
      "Screens should read like a small number of strong regions rather than a pile of loose widgets."
  },
  {
    parent: "<Section>",
    allows: "text, links, actions, animations, and nested layout",
    body:
      "A section should hold one idea or one workflow step and expose only the items needed inside that region."
  },
  {
    parent: "<AsciiAnimation>",
    allows: "only <Frame> children",
    body:
      "Animation stays declarative and transport-safe by carrying frame data and playback metadata instead of executable logic."
  },
  {
    parent: "<Row>",
    allows: "small leaf components or compact nested panels",
    body: "Rows are for tightly coupled items. Wide prose and large boxes should usually stay in columns."
  }
];

export const examples = [
  {
    name: "Landing",
    path: "examples/landing/index.erza",
    summary: "A terminal-native splash surface meant for recording and homepage storytelling."
  },
  {
    name: "Tasks",
    path: "examples/tasks/app.erza",
    summary: "Backend-fed task workflow with page history and remote docs links."
  },
  {
    name: "Greetings",
    path: "examples/greetings/index.erza",
    summary: "A small directory entrypoint with stateful backend changes."
  },
  {
    name: "Animation",
    path: "examples/animation/index.erza",
    summary: "A local lab for the new AsciiAnimation component and runtime tick loop."
  }
];

export const patterns = [
  {
    name: "Operator Dashboard",
    summary: "A boxed overview with status strips, urgent queues, and a detail rail.",
    regions: "Hero metrics, active queue, alerts, audit trail"
  },
  {
    name: "Docs Reader",
    summary: "Dense reference content with navigation, code samples, and capability notes.",
    regions: "Overview, topic panels, code windows, appendix"
  },
  {
    name: "Inbox + Inspector",
    summary: "A list-first workflow with one active document and a side channel for metadata.",
    regions: "Folder rail, message list, reading pane, inspector"
  },
  {
    name: "Settings Surface",
    summary: "Low-drama forms, toggles, and state explanations without browser settings sludge.",
    regions: "Category nav, fields, confirmation area, recent changes"
  },
  {
    name: "Launch Pad",
    summary: "Command surfaces, recent destinations, and quick open flows for remote apps.",
    regions: "Primary actions, saved endpoints, help, session status"
  },
  {
    name: "Animation Lab",
    summary: "A place for motion components, playback controls, and frame fallbacks.",
    regions: "Poster frame, live runtime note, frame strip, open questions"
  }
];

export const capabilityMatrix = [
  {
    feature: "Boxed panel layout",
    runtime: "works",
    docs: "works",
    remote: "works",
    erzanet: "ready"
  },
  {
    feature: "Multi-page information architecture",
    runtime: "works",
    docs: "works",
    remote: "works",
    erzanet: "ready"
  },
  {
    feature: "AsciiAnimation playback",
    runtime: "works",
    docs: "poster fallback",
    remote: "poster fallback",
    erzanet: "needs transport shape"
  },
  {
    feature: "Complex nested composition",
    runtime: "partial",
    docs: "works",
    remote: "partial",
    erzanet: "needs component schema"
  },
  {
    feature: "Stateful remote interaction",
    runtime: "local only",
    docs: "n/a",
    remote: "read only",
    erzanet: "core future work"
  }
];

export const labTracks = [
  {
    title: "Remote Viewer Gaps",
    body: "Use the hosted site as a checklist for what the HTML scraper still flattens, loses, or over-groups."
  },
  {
    title: "Component System Pressure",
    body:
      "Use the richer pages to discover which panels should become first-class components instead of staying ad hoc markup patterns."
  },
  {
    title: "Motion Without Browser Baggage",
    body: "Use AsciiAnimation to define how much motion can live in a TUI without turning into terminal abuse."
  }
];

export const protocolSteps = [
  {
    step: "1",
    title: "Resolve a domain",
    body: "`erza example.com` assumes HTTPS and asks the server for an erza app, not a browser document."
  },
  {
    step: "2",
    title: "Fetch a screen tree",
    body: "The server returns a safe section-first screen tree the client can render locally."
  },
  {
    step: "3",
    title: "Send actions back",
    body: "Links and actions post structured events back to the server while client-side history stays local."
  },
  {
    step: "4",
    title: "Rerender in place",
    body: "The client receives the next screen or a diff and updates the local terminal session."
  }
];

export const safetyPoints = [
  "Do not ship arbitrary backend code to the client.",
  "Keep the wire format declarative and terminal-native.",
  "Preserve normal backend integration over HTTPS.",
  "Avoid inheriting browser compatibility scope by accident."
];

export const animationFrames = [
  { title: "Frame 1", art: "+---------+\n|*        |\n|  erza   |\n+---------+" },
  { title: "Frame 2", art: "+---------+\n|   *     |\n|  erza   |\n+---------+" },
  { title: "Frame 3", art: "+---------+\n|      *  |\n|  erza   |\n+---------+" }
];

export const animationMarkup = `<AsciiAnimation label="Signal" fps="6">
  <Frame>
  +---------+
  |*        |
  |  erza   |
  +---------+
  </Frame>
  <Frame>
  +---------+
  |   *     |
  |  erza   |
  +---------+
  </Frame>
  <Frame>
  +---------+
  |      *  |
  |  erza   |
  +---------+
  </Frame>
</AsciiAnimation>`;

export const protocolWireFormat = `GET  /app
Accept: application/erza+json

200 OK
Content-Type: application/erza+json

{
  "session": "abc123",
  "screen": { "title": "Inbox", "children": [...] },
  "actions": { "open_message": { "method": "POST", "href": "/actions/open" } }
}

POST /actions/open
Content-Type: application/json

{ "session": "abc123", "message_id": 42 }`;
