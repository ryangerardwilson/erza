"use client";

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
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path fill="currentColor" d="M9 9h10v12H9zM5 3h10v2H7v10H5z" />
    </svg>
  );
}

export default function CopyDocsButton({ content }) {
  async function handleClick() {
    try {
      await writeClipboard(content);
    } catch {
      // Keep the UI identical to the reference surface; failure stays silent.
    }
  }

  return (
    <button
      type="button"
      className="docs-panel-copy"
      onClick={handleClick}
      aria-label="Copy markdown"
      title="Copy markdown"
    >
      <CopyMark />
    </button>
  );
}
