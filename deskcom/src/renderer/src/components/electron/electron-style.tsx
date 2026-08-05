import { SystemStyleObject } from '@chakra-ui/react';

export const inputSubtitleStyles = {
  container: {
    maxW: 'fit-content',
    position: 'absolute' as const,
    bottom: '20px',
    right: '20px',
    left: 'auto',
    transform: 'none',
    zIndex: 1000,
    userSelect: 'none',
    willChange: 'transform',
    padding: 0,
  },

  box: {
    w: '420px',
    rounded: 'xl',
    overflow: 'visible',
    boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
    bg: '#1a1a2e',
    border: '1px solid',
    borderColor: '#2a2a4a',
    css: { WebkitUserSelect: 'none' },
  },

  messageStack: {
    p: '3',
    gap: 1,
    alignItems: 'stretch',
    justify: 'flex-end',
  },

  messageText: {
    color: '#e0e0ff',
    fontSize: 'sm',
    lineHeight: '1.5',
    transition: 'all 0.3s',
  },

  statusBox: {
    bg: '#16162a',
    p: '3',
    borderTop: '1px solid',
    borderColor: '#2a2a4a',
  },

  statusText: {
    fontSize: 'xs',
    color: '#c0c0e0',
    transition: 'all 0.3s',
  },

  iconButton: {
    size: 'xs',
    variant: 'ghost',
    color: '#c0c0e0',
    _hover: { bg: '#2a2a4a', color: '#ffffff' },
  },

  inputBox: {
    bg: '#16162a',
    borderTop: '1px solid',
    borderColor: '#2a2a4a',
  },

  input: {
    size: 'sm',
    bg: '#0f0f23',
    color: '#e0e0ff',
    _placeholder: { color: '#555577' },
    border: '1px solid',
    borderColor: '#2a2a4a',
    _focus: {
      borderColor: '#6666aa',
      outline: 'none',
      boxShadow: '0 0 0 1px #6666aa',
    },
    _hover: { borderColor: '#3a3a5a' },
    flex: '1',
    rounded: 'md',
  },

  sendButton: {
    p: '1.5',
    bg: '#2a2a4a',
    rounded: 'lg',
    _hover: { bg: '#3a3a5a' },
    transition: 'colors',
    color: '#c0c0e0',
    size: 'sm',
  },

  draggableContainer: (isDragging: boolean): SystemStyleObject => ({
    cursor: isDragging ? 'grabbing' : 'grab',
    transition: isDragging ? 'none' : 'transform 0.1s ease',
    _active: { cursor: 'grabbing' },
  }),

  closeButton: {
    size: '2xs',
    minW: '6',
    height: '6',
    padding: 0,
    variant: 'ghost',
    color: '#8888bb',
    bg: 'transparent',
    _hover: {
      bg: '#2a2a4a',
      color: '#ffffff',
    },
  },
} as const;
