import { Box } from '@chakra-ui/react';
import type { SystemStyleObject } from '@chakra-ui/react';
import { WashiTape } from './washi-tape';

interface SketchCardProps {
  children: React.ReactNode;
  label?: string;
  tapeColor?: string;
  css?: SystemStyleObject;
  onClick?: () => void;
  cursor?: string;
}

/**
 * Paper card with a hand-drawn outline: irregular per-corner radius,
 * a slightly rotated "ink" border, and an optional washi-tape header.
 */
export function SketchCard({ children, label, tapeColor, css, onClick, cursor }: SketchCardProps) {
  return (
    <Box
      position="relative"
      bg="var(--sk-paper-deep)"
      borderRadius="var(--sk-radius-card)"
      border="1.5px solid var(--sk-outline)"
      transform="rotate(var(--sk-rotate))"
      boxShadow="0 2px 6px rgba(0,0,0,0.18)"
      onClick={onClick}
      cursor={cursor}
      css={{
        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
        _hover: {
          transform: 'rotate(var(--sk-rotate)) translateY(-1px)',
          boxShadow: '0 4px 10px rgba(0,0,0,0.22)',
        },
        ...css,
      }}
    >
      {label && <WashiTapeLabel label={label} color={tapeColor} />}
      {children}
    </Box>
  );
}

function WashiTapeLabel({ label, color }: { label: string; color?: string }) {
  return <WashiTape label={label} color={color} />;
}
