import { Box, Text, VStack } from '@chakra-ui/react';

function About() {
  return (
    <VStack align="start" spaceY={4}>
      <Box>
        <Text fontSize="lg" fontWeight="bold" color="#e0e0ff">Yakult My Bini</Text>
        <Text fontSize="sm" color="#8888bb">v1.2.1</Text>
      </Box>
      <Text fontSize="sm" color="#a0a0cc">
        Agentic AI Companion — a desktop AI companion powered by LLM and Live2D.
      </Text>
      <Text fontSize="xs" color="#666688">
        Built on open-source foundations.
      </Text>
    </VStack>
  );
}

export default About;
