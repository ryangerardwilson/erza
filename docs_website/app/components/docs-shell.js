import { DocsShell as SharedDocsShell } from "@ryangerardwilson/docs-shell";

import { getDocPageData, getDocsTabs } from "@/lib/readme-docs";

const utilityLinks = [
  {
    href: "https://ryangerardwilson.com/",
    label: "About the Author",
    kind: "button",
    newTab: true
  },
  {
    href: "https://github.com/ryangerardwilson/erza",
    label: "GitHub",
    kind: "icon",
    icon: "github",
    newTab: true
  }
];

function docPayload() {
  return getDocsTabs().map((tab) => {
    const page = getDocPageData(tab.slug);
    return {
      ...tab,
      title: tab.label,
      commandLabel: page.fileName,
      content: page.content
    };
  });
}

export default function DocsShell({ activeSlug = "readme" }) {
  return (
    <SharedDocsShell
      initialSlug={activeSlug}
      docs={docPayload()}
      utilityLinks={utilityLinks}
      titleSuffix="erza docs"
    />
  );
}
