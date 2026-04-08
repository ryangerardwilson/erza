"use client";

import { useState } from "react";

export default function CopyCommand({ value, className = "code-block code-block-command" }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="copy-command">
      <pre className={className}>
        <code>{value}</code>
      </pre>
      <button className="copy-button" type="button" onClick={handleCopy}>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
