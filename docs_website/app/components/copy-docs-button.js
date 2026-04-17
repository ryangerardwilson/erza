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

function CopyMark() {
  return (
    <svg className="docs-copy-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M3 1.75A1.75 1.75 0 0 1 4.75 0h6.5C12.216 0 13 .784 13 1.75V3h.25A1.75 1.75 0 0 1 15 4.75v8.5A1.75 1.75 0 0 1 13.25 15h-6.5A1.75 1.75 0 0 1 5 13.25V12H4.75A1.75 1.75 0 0 1 3 10.25v-8.5ZM6.5 12v1.25c0 .138.112.25.25.25h6.5a.25.25 0 0 0 .25-.25v-8.5a.25.25 0 0 0-.25-.25h-6.5a.25.25 0 0 0-.25.25V12Zm-2-1.75c0 .138.112.25.25.25H5V4.75A1.75 1.75 0 0 1 6.75 3h4.75V1.75a.25.25 0 0 0-.25-.25h-6.5a.25.25 0 0 0-.25.25v8.5Z"
      />
    </svg>
  );
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
      <CopyMark />
      <span>{label}</span>
    </button>
  );
}
