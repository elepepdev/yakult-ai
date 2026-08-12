import { useEffect, useState } from 'react';

export function useTypewriter(text: string): string {
  const [revealed, setRevealed] = useState('');
  useEffect(() => {
    // The AI response streams in chunks, so `text` grows over time. If the new
    // text is a continuation of what's already revealed, keep typing from where
    // we are instead of restarting from scratch; only reset on a brand-new message.
    const continuing = revealed.length > 0 && text.startsWith(revealed);
    if (!continuing) {
      setRevealed('');
    }
    let i = continuing ? revealed.length : 0;
    // Reveal the whole text in ~1.2s, but in batches of a few chars per tick at
    // most 16ms apart (~60 state updates/sec) instead of one setState per char,
    // which hammered the whole subtitle box for long messages.
    const TICK_MS = 16;
    const TICKS = Math.round(1200 / TICK_MS);
    const charsPerTick = Math.max(1, Math.round(text.length / TICKS));
    const interval = setInterval(() => {
      i = Math.min(text.length, i + charsPerTick);
      setRevealed(text.slice(0, i));
      if (i >= text.length) clearInterval(interval);
    }, TICK_MS);
    return () => clearInterval(interval);
  }, [text]);
  return revealed;
}
