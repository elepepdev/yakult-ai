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
    bg: 'rgba(20, 20, 40, 0.65)',
    backdropFilter: 'blur(18px)',
    WebkitBackdropFilter: 'blur(18px)',
    border: '1px solid',
    borderColor: 'rgba(255,255,255,0.2)',
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
    bg: 'rgba(255,255,255,0.02)',
    p: '3',
    borderTop: '1px solid',
    borderColor: 'rgba(255,255,255,0.1)',
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
    bg: 'rgba(255,255,255,0.02)',
    borderTop: '1px solid',
    borderColor: 'rgba(255,255,255,0.1)',
  },

  input: {
    size: 'sm',
    bg: 'rgba(0,0,0,0.25)',
    color: '#e0e0ff',
    _placeholder: { color: '#7777aa' },
    border: '1px solid',
    borderColor: 'rgba(255,255,255,0.2)',
    _focus: {
      borderColor: 'rgba(120,120,220,0.6)',
      outline: 'none',
      boxShadow: '0 0 0 1px rgba(120,120,220,0.4)',
    },
    _hover: { borderColor: 'rgba(255,255,255,0.3)' },
    flex: '1',
    rounded: 'md',
  },

  sendButton: {
    p: '1.5',
    bg: 'rgba(120,120,220,0.35)',
    rounded: 'lg',
    _hover: { bg: 'rgba(120,120,220,0.5)' },
    transition: 'colors',
    color: '#e0e0ff',
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
