import { useState, useEffect, useCallback, useRef } from 'react';
import { getPlatform } from '@/platforms';

export interface MentionEntry {
  name: string;
  path: string;
  isDir: boolean;
}

export interface MentionAPI {
  suggestions: MentionEntry[];
  selectedIndex: number;
  isOpen: boolean;
  cursorRef: React.MutableRefObject<number>;
  handleKeyDown: (e: React.KeyboardEvent) => boolean;
  insertMention: (entry: MentionEntry) => void;
  mentionStart: number;
  closeMention: () => void;
}

const MAX_SUGGESTIONS = 20;

export function useMention(
  inputText: string,
  setInputText: (value: string) => void,
  inputRef: React.RefObject<HTMLInputElement | null>,
): MentionAPI {
  const [suggestions, setSuggestions] = useState<MentionEntry[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [mentionStart, setMentionStart] = useState(-1);
  const cursorRef = useRef<number>(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const homeDirRef = useRef<string>('');

  useEffect(() => {
    getPlatform().getHomeDir().then((homeDir: string) => {
      homeDirRef.current = homeDir;
    });
  }, []);

  const closeMention = useCallback(() => {
    setIsOpen(false);
    setSuggestions([]);
    setSelectedIndex(0);
    setMentionStart(-1);
  }, []);

  useEffect(() => {
    const textBeforeCursor = inputText.slice(0, cursorRef.current);
    const atIndex = textBeforeCursor.lastIndexOf('@');

    if (atIndex === -1) {
      closeMention();
      return;
    }

    const afterAt = textBeforeCursor.slice(atIndex + 1);

    if (afterAt.includes(' ') || afterAt.includes('\n')) {
      closeMention();
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const result = await getPlatform().listDirectory(afterAt);
        if (result.success) {
          const limited = result.entries.slice(0, MAX_SUGGESTIONS);
          setSuggestions(limited);
          setSelectedIndex(0);
          setMentionStart(atIndex);
          setIsOpen(limited.length > 0);
        } else {
          closeMention();
        }
      } catch {
        closeMention();
      }
    }, 100);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [inputText]);

  const selectNext = useCallback(() => {
    setSelectedIndex((prev) => Math.min(prev + 1, suggestions.length - 1));
  }, [suggestions.length]);

  const selectPrev = useCallback(() => {
    setSelectedIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const insertMention = useCallback(
    (entry: MentionEntry) => {
      if (mentionStart === -1) return;
      const homeDir = homeDirRef.current;
      const displayPath = homeDir && entry.path.startsWith(homeDir)
        ? '~' + entry.path.slice(homeDir.length)
        : entry.path;
      const before = inputText.slice(0, mentionStart);
      const after = inputText.slice(cursorRef.current);
      const newText = `${before}@${displayPath} ${after}`;
      setInputText(newText);
      closeMention();
      requestAnimationFrame(() => {
        const el = inputRef.current;
        if (el) {
          const newCursor = mentionStart + displayPath.length + 2;
          el.setSelectionRange(newCursor, newCursor);
          el.focus();
        }
      });
    },
    [inputText, mentionStart, setInputText, closeMention, inputRef],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): boolean => {
      if (!isOpen) return false;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectNext();
        return true;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectPrev();
        return true;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (suggestions[selectedIndex]) {
          insertMention(suggestions[selectedIndex]);
        }
        return true;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        closeMention();
        return true;
      }
      return false;
    },
    [isOpen, selectNext, selectPrev, suggestions, selectedIndex, insertMention, closeMention],
  );

  return {
    suggestions,
    selectedIndex,
    isOpen,
    cursorRef,
    handleKeyDown,
    insertMention,
    mentionStart,
    closeMention,
  };
}
