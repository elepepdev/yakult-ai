import { Text } from '@chakra-ui/react';

interface MarkerTextProps {
  children: React.ReactNode;
  size?: string;
  rotate?: string;
}

/**
 * Hand-written text with a marker-pen (spidol) outline: ink fill,
 * marker-colored stroke around the letterforms plus a faint offset shadow.
 */
export function MarkerText({ children, size = 'lg', rotate = '-2deg' }: MarkerTextProps) {
  return (
    <Text
      fontFamily="var(--sk-font-hand)"
      fontSize={size}
      fontWeight="600"
      color="var(--sk-ink)"
      transform={`rotate(${rotate})`}
      userSelect="none"
      lineHeight="1"
      css={{
        WebkitTextStroke: '1.1px var(--sk-marker)',
        textShadow:
          '1.5px 1.5px 0 var(--sk-marker), -1px -1px 0 var(--sk-marker), 1.5px -1px 0 var(--sk-marker), -1px 1.5px 0 var(--sk-marker)',
      }}
    >
      {children}
    </Text>
  );
}
