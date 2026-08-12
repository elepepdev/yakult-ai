import { useEffect, useState } from 'react';

export function useTypewriter(text: string): string {
  const [revealed, setRevealed] = useState('');
  useEffect(() => {
    setRevealed('');
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setRevealed(text.slice(0, i));
      if (i >= text.length) clearInterval(interval);
    }, Math.max(4, Math.round(text.length / 40)));
    return () => clearInterval(interval);
  }, [text]);
  return revealed;
}
