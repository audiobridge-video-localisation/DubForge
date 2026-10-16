import { useEffect, useState } from "react";

// Types each phrase, holds, deletes, then moves to the next.
export default function useTypewriter(phrases, speed = 55) {
  const [text, setText] = useState("");

  useEffect(() => {
    let phrase = 0,
      i = 0,
      dir = 1,
      hold = 0;
    const id = setInterval(() => {
      if (hold > 0) {
        hold--;
        return;
      }
      i += dir;
      setText(phrases[phrase].slice(0, i));
      if (i === phrases[phrase].length) {
        dir = -1;
        hold = 24;
      } else if (i === 0) {
        dir = 1;
        phrase = (phrase + 1) % phrases.length;
        hold = 6;
      }
    }, speed);
    return () => clearInterval(id);
  }, [phrases, speed]);

  return text;
}
