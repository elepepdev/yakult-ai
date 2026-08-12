import { Box, Text } from '@chakra-ui/react';

interface WashiTapeProps {
  label?: string;
  color?: string;
  rotate?: string;
  width?: string;
}

export function WashiTape({ label, color, rotate = '-2deg', width = 'auto' }: WashiTapeProps) {
  return (
    <Box
      position="absolute"
      top="-9px"
      left="24px"
      transform={`rotate(${rotate})`}
      bg={color || 'var(--sk-marker)'}
      px={label ? 2.5 : 4}
      py={label ? '1px' : '3px'}
      borderRadius="1px"
      boxShadow="0 1px 2px rgba(0,0,0,0.25)"
      opacity={0.85}
      width={width}
      zIndex={1}
      pointerEvents="none"
      css={{
        backgroundImage:
          'repeating-linear-gradient(45deg, rgba(255,255,255,0.25) 0px, rgba(255,255,255,0.25) 2px, transparent 2px, transparent 5px)',
      }}
    >
      {label && (
        <Text
          fontFamily="var(--sk-font-hand)"
          fontSize="sm"
          fontWeight="600"
          color="rgba(255,255,255,0.95)"
          lineHeight="1.2"
          userSelect="none"
        >
          {label}
        </Text>
      )}
    </Box>
  );
}
