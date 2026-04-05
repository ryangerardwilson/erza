(() => {
  const target = document.querySelector(".typewriter-target");
  if (!target) {
    return;
  }
  const rotator = target.closest(".story-rotator");

  let phrases = [];
  try {
    phrases = JSON.parse(target.dataset.phrases || "[]");
  } catch {
    phrases = [];
  }

  if (phrases.length === 0) {
    return;
  }

  let phraseIndex = 0;
  let charIndex = 0;
  let deleting = false;

  const holdFullMs = 2100;
  const holdEmptyMs = 320;
  const typingMs = 68;
  const deletingMs = 34;

  const reserveHeight = () => {
    if (!rotator) {
      return;
    }

    const current = target.textContent;
    let maxHeight = 0;

    for (const phrase of phrases) {
      target.textContent = phrase;
      maxHeight = Math.max(maxHeight, rotator.getBoundingClientRect().height);
    }

    target.textContent = current;
    rotator.style.minHeight = `${Math.ceil(maxHeight)}px`;
  };

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

  reserveHeight();
  window.addEventListener("resize", reserveHeight);
  target.textContent = "";
  window.setTimeout(tick, 360);
})();
