import { memo } from 'react';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { Live2D } from '@/components/canvas/live2d';
import VRMCanvas from '@/components/canvas/vrm/VRMCanvas';
import OrbCanvas from '@/components/canvas/orb/OrbCanvas';

/**
 * ModelRenderer switches between Live2D, VRM, and Orb rendering
 * based on the model type from config/model_info.
 */
export const ModelRenderer = memo(
  (): JSX.Element | null => {
    const { modelInfo } = useLive2DConfig();
    const modelType = modelInfo?.type || 'live2d';

    // Don't mount any model renderer until the server has told us which
    // model to show. Mounting Live2D before model_info arrives makes the
    // Cubism render loop crash on a null model (getDrawableCount).
    if (!modelInfo?.url) {
      return null;
    }

    if (modelType === 'vrm') {
      return <VRMCanvas />;
    }

    if (modelType === 'orb') {
      return <OrbCanvas />;
    }

    // Default to Live2D
    return <Live2D />;
  },
);

ModelRenderer.displayName = 'ModelRenderer';

export default ModelRenderer;
