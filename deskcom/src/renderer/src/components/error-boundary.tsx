import { Component, type ReactNode, type ErrorInfo } from 'react';
import { Box, Text, Button } from '@chakra-ui/react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Box
          position="fixed"
          top={0}
          left={0}
          w="100vw"
          h="100vh"
          bg="gray.900"
          color="white"
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          p={8}
          zIndex={9999}
        >
          <Text fontSize="xl" fontWeight="bold" mb={4}>
            Terjadi Kesalahan
          </Text>
          <Text fontSize="sm" mb={4} maxW="600px" textAlign="center" color="gray.400">
            {this.state.error?.message || 'Terjadi kesalahan yang tidak terduga.'}
          </Text>
          <Text fontSize="xs" mb={6} maxW="600px" textAlign="center" color="gray.500" fontFamily="monospace">
            {this.state.error?.stack?.split('\n').slice(0, 3).join('\n')}
          </Text>
          <Button
            onClick={this.handleRetry}
            colorScheme="blue"
            size="lg"
          >
            Coba Lagi
          </Button>
        </Box>
      );
    }

    return this.props.children;
  }
}
