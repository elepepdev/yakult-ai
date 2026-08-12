import { Box, Text } from '@chakra-ui/react';
import { useEffect, useRef, useState } from 'react';
import { useSubtitle } from '@/context/subtitle-context';
import { FormattedText } from '@/components/ui/formatted-text';
import { useVrmHeadPosition } from '@/hooks/utils/use-vrm-head-position';

type BubblePhase = 'hidden' | 'showing' | 'popping';

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

/**
 * Comic-style thought bubble shown above the character's head for
 * subconscious / dream ("melamun") text. It pops in when text arrives
 * and bursts apart when the user focuses the input box.
 */
export function ThoughtBubble() {
  const { subconsciousText, dismissSubconscious } = useSubtitle();
  const reducedMotion = usePrefersReducedMotion();
  const headPos = useVrmHeadPosition();
  const [phase, setPhase] = useState<BubblePhase>('hidden');
  const [displayText, setDisplayText] = useState('');
  const popTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // New thought arrives → show
  useEffect(() => {
    if (subconsciousText) {
      setDisplayText(subconsciousText);
      setPhase('showing');
    }
  }, [subconsciousText]);

  // Text cleared (dismissSubconscious) → burst apart, then unmount
  useEffect(() => {
    if (!subconsciousText && phase === 'showing') {
      setPhase('popping');
      popTimer.current = setTimeout(() => {
        setDisplayText('');
        setPhase('hidden');
      }, 320);
    }
  }, [subconsciousText, phase]);

  useEffect(() => {
    return () => {
      if (popTimer.current) clearTimeout(popTimer.current);
    };
  }, []);

  if (phase === 'hidden' || !displayText) return null;

  const animation = reducedMotion
    ? 'none'
    : phase === 'popping'
      ? 'sk-pop 0.32s ease-in forwards'
      : 'sk-pop-in 0.25s ease-out';

  // Anchor above the character's head (head center px → bubble centered, with
  // the ~40px thought-trail reaching down toward the head). Fall back to the
  // default top-center position until the model is loaded.
  const BUBBLE_W = 340;
  const anchorStyle = headPos
    ? {
        left: `${Math.max(8, Math.min(window.innerWidth - BUBBLE_W - 8, headPos.x - BUBBLE_W / 2))}px`,
        top: 'auto',
        bottom: `${Math.max(8, window.innerHeight - headPos.y + 44)}px`,
        transform: 'none',
      }
    : { top: '32vh', left: '50%', transform: 'translateX(-50%)' };

  return (
    <Box
      position="fixed"
      zIndex={500}
      pointerEvents="none"
      style={anchorStyle}
      css={{ animation }}
    >
      {/* Thought trail — small circles descending toward the head */}
      <Box
        position="absolute"
        left="50%"
        bottom="-38px"
        transform="translateX(-50%)"
        display="flex"
        flexDirection="column"
        alignItems="center"
        gap="5px"
      >
        <Box w="12px" h="12px" borderRadius="full" bg="var(--sk-outline)" />
        <Box w="8px" h="8px" borderRadius="full" bg="var(--sk-outline)" />
        <Box w="5px" h="5px" borderRadius="full" bg="var(--sk-outline)" />
      </Box>

      <Box
        bg="var(--sk-paper)"
        border="1.5px solid"
        borderColor="var(--sk-outline)"
        borderRadius="var(--sk-radius-card)"
        boxShadow="0 6px 24px rgba(0,0,0,0.35)"
        px={5}
        py={3}
        maxW="340px"
        transform="rotate(var(--sk-rotate))"
      >
        <Text
          color="var(--sk-ink)"
          fontSize="md"
          fontFamily="var(--sk-font-subtitle)"
          lineHeight="1.5"
          textAlign="center"
          whiteSpace="pre-wrap"
        >
          <FormattedText text={displayText} />
        </Text>
      </Box>
    </Box>
  );
}

export default ThoughtBubble;
