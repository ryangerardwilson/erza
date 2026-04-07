"use client";

import { useEffect, useRef, useState } from "react";

export default function TypewriterHero({ phrases }) {
  const rotatorRef = useRef(null);
  const targetRef = useRef(null);
  const [text, setText] = useState(phrases[0] ?? "");

  useEffect(() => {
    const rotator = rotatorRef.current;
    if (!rotator || phrases.length === 0) {
      return undefined;
    }

    const measure = document.createElement("span");
    measure.className = "typewriter-target";
    measure.style.position = "absolute";
    measure.style.visibility = "hidden";
    measure.style.pointerEvents = "none";
    measure.style.inset = "0 auto auto 0";
    measure.style.width = "100%";
    rotator.appendChild(measure);

    const reserveHeight = () => {
      const computed = window.getComputedStyle(measure);
      const lineHeight =
        Number.parseFloat(computed.lineHeight) || Number.parseFloat(computed.fontSize) * 1.05 || 0;
      const minimumHeight = lineHeight * 2;
      let maxHeight = 0;
      for (const phrase of phrases) {
        measure.textContent = phrase;
        maxHeight = Math.max(maxHeight, measure.getBoundingClientRect().height);
      }
      rotator.style.minHeight = `${Math.ceil(Math.max(maxHeight, minimumHeight))}px`;
    };

    reserveHeight();
    window.addEventListener("resize", reserveHeight);

    let phraseIndex = 0;
    let charIndex = 0;
    let deleting = false;
    let timerId;

    const holdFullMs = 2100;
    const holdEmptyMs = 320;
    const typingMs = 86;

    const tick = () => {
      const phrase = phrases[phraseIndex];

      if (!deleting) {
        charIndex = Math.min(charIndex + 1, phrase.length);
        setText(phrase.slice(0, charIndex));
        if (charIndex === phrase.length) {
          deleting = true;
          timerId = window.setTimeout(tick, holdFullMs);
          return;
        }
        timerId = window.setTimeout(tick, typingMs);
        return;
      }

      charIndex = 0;
      setText("");
      deleting = false;
      phraseIndex = (phraseIndex + 1) % phrases.length;
      timerId = window.setTimeout(tick, holdEmptyMs);
    };

    setText("");
    timerId = window.setTimeout(tick, 360);

    return () => {
      window.clearTimeout(timerId);
      window.removeEventListener("resize", reserveHeight);
      rotator.removeChild(measure);
    };
  }, [phrases]);

  return (
    <div className="story-stack">
      <p className="story-prefix">What if</p>
      <h1 className="story-rotator" ref={rotatorRef}>
        <span className="typewriter-target" ref={targetRef}>
          {text}
        </span>
      </h1>
    </div>
  );
}
