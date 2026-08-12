import { Box } from '@chakra-ui/react';
import SchemaForm from './schema-form';

function System() {
  return (
    <Box spaceY={5}>
      <SchemaForm rootPath="system_config" />
    </Box>
  );
}

export default System;
