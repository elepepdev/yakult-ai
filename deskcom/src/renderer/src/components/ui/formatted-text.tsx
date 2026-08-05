import { Fragment, useState, useCallback } from 'react';
import { Box, Text } from '@chakra-ui/react';
import { LuCopy, LuCheck } from 'react-icons/lu';

interface FormattedTextProps {
  text: string;
  as?: 'span' | 'div';
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [code]);

  return (
    <Box
      as="pre"
      my={2}
      p={3}
      bg="#0d0d1f"
      border="1px solid"
      borderColor="#2a2a5a"
      rounded="md"
      fontSize="xs"
      fontFamily="mono"
      color="#c0c0ff"
      overflowX="auto"
      position="relative"
      css={{
        '&::-webkit-scrollbar': { height: '4px' },
        '&::-webkit-scrollbar-track': { bg: 'transparent' },
        '&::-webkit-scrollbar-thumb': { bg: '#2a2a5a', borderRadius: '2px' },
      }}
    >
      {language && (
        <Text
          position="absolute"
          top={1}
          right={8}
          fontSize="2xs"
          color="#555588"
          textTransform="uppercase"
        >
          {language}
        </Text>
      )}
      <Box
        position="absolute"
        top={1}
        right={1}
        cursor="pointer"
        color="#555588"
        _hover={{ color: '#c0c0ff' }}
        onClick={handleCopy}
      >
        {copied ? <LuCheck size={12} /> : <LuCopy size={12} />}
      </Box>
      <Box pt={language ? 4 : 0}>
        <Text as="code" whiteSpace="pre" fontSize="xs">
          {code}
        </Text>
      </Box>
    </Box>
  );
}

function parseInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('*') && part.endsWith('*')) {
      const inner = part.slice(1, -1);
      return <strong key={i}>{inner}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      const inner = part.slice(1, -1);
      return (
        <Box
          as="code"
          key={i}
          bg="#0d0d1f"
          px={1}
          rounded="sm"
          fontSize="xs"
          fontFamily="mono"
          color="#c0c0ff"
        >
          {inner}
        </Box>
      );
    }
    if (!part) return null;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

function parseText(text: string): React.ReactNode[] {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    const codeMatch = part.match(/^```(\w*)\n?([\s\S]*?)```$/);
    if (codeMatch) {
      const language = codeMatch[1] || '';
      const code = codeMatch[2];
      return <CodeBlock key={i} code={code} language={language} />;
    }
    if (!part) return null;
    return <Fragment key={i}>{parseInline(part)}</Fragment>;
  });
}

export function FormattedText({ text, as: Tag = 'span' }: FormattedTextProps) {
  return <Tag>{parseText(text)}</Tag>;
}
