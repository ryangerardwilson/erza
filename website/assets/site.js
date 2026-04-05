(() => {
  const target = document.querySelector(".typewriter-target");
  if (!target) {
    return;
  }

  const lines = Array.from(document.querySelectorAll(".story-line"))
    .map((node) => node.textContent.trim())
    .filter(Boolean);

  const phrases = lines
    .map((line) => line.replace(/^What if\s+/i, ""))
    .filter(Boolean);

  if (phrases.length === 0) {
    return;
  }

  let phraseIndex = 0;
  let charIndex = 0;
  let deleting = false;

  const holdFullMs = 1600;
  const holdEmptyMs = 220;
  const typingMs = 42;
  const deletingMs = 24;

  const tick = () => {
    const phrase = phrases[phraseIndex];

    if (!deleting) {
      charIndex = Math.min(charIndex + 1, phrase.length);
      target.textContent = phrase.slice(0, charIndex);
      if (charIndex === phrase.length) {
        deleting = true;
        window.setTimeout(tick, holdFullMs);
        return;
      }
      window.setTimeout(tick, typingMs);
      return;
    }

    charIndex = Math.max(charIndex - 1, 0);
    target.textContent = phrase.slice(0, charIndex);
    if (charIndex === 0) {
      deleting = false;
      phraseIndex = (phraseIndex + 1) % phrases.length;
      window.setTimeout(tick, holdEmptyMs);
      return;
    }
    window.setTimeout(tick, deletingMs);
  };

  target.textContent = "";
  window.setTimeout(tick, 240);
})();
