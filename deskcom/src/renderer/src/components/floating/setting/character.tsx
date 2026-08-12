import { Box } from '@chakra-ui/react';
import SchemaForm from './schema-form';

function Character() {
  return (
    <Box spaceY={5}>
      <SchemaForm
        rootPath="character_config"
        only={['conf_name', 'conf_uid', 'live2d_model_name', 'model_type', 'character_name', 'human_name', 'avatar', 'persona_prompt']}
      />
    </Box>
  );
}

export default Character;
