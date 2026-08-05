import { memo } from 'react';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { Live2D } from '@/components/canvas/live2d';
import VRMCanvas from '@/components/canvas/vrm/VRMCanvas';

/**
 * ModelRenderer switches between Live2D and VRM rendering
 * based on the model type from config/model_info.
 */
export const ModelRenderer = memo(
  (): JSX.Element => {
    const { modelInfo } = useLive2DConfig();
    const modelType = modelInfo?.type || 'live2d';

    if (modelType === 'vrm') {
      return <VRMCanvas />;
    }

    // Default to Live2D
    return <Live2D />;
  },
);

ModelRenderer.displayName = 'ModelRenderer';

export default ModelRenderer;
