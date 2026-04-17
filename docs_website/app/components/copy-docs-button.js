"use client";

import { useEffect, useRef, useState } from "react";

async function writeClipboard(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

export default function CopyDocsButton({ content, fileName }) {
  const [status, setStatus] = useState("idle");
  const resetTimer = useRef(null);

  useEffect(() => {
    return () => {
      if (resetTimer.current) {
        clearTimeout(resetTimer.current);
      }
    };
  }, []);

  async function handleClick() {
    try {
      await writeClipboard(content);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }

    if (resetTimer.current) {
      clearTimeout(resetTimer.current);
    }
    resetTimer.current = window.setTimeout(() => {
      setStatus("idle");
    }, 1600);
  }

  const label = status === "copied" ? "Copied" : status === "failed" ? "Retry" : "Copy";

  return (
    <button
      type="button"
      className="docs-copy-button"
      onClick={handleClick}
      aria-label={`Copy ${fileName} to the clipboard`}
      title={`Copy ${fileName}`}
    >
      {label}
    </button>
  );
}
