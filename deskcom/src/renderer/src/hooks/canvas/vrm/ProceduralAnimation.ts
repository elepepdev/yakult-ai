// @ts-nocheck
import type { VRM } from '@pixiv/three-vrm';
import type { VRMHumanoid } from '@pixiv/three-vrm';

const sin = Math.sin;

function setBone(
  humanoid: VRMHumanoid,
  name: string,
  rot: { x?: number; y?: number; z?: number },
) {
  const node = humanoid.getNormalizedBoneNode(name);
  if (!node) return;
  if (rot.x !== undefined) node.rotation.x = rot.x;
  if (rot.y !== undefined) node.rotation.y = rot.y;
  if (rot.z !== undefined) node.rotation.z = rot.z;
}

export class ProceduralAnimation {
  private vrm: VRM;
  private elapsedTime = 0;

  constructor(vrm: VRM) {
    this.vrm = vrm;
  }

  public update(delta: number) {
    this.elapsedTime += delta;

    if (!this.vrm?.humanoid) return;

    const h = this.vrm.humanoid;
    const t = this.elapsedTime;

    // Standing pose (T-pose → natural A-pose) + subtle idle breathing
    // DO NOT rotate neck here — spring bones (hair) and lookAt system control the head
    setBone(h, 'spine', { x: 0.05 - 0.015 * sin(t * 1.5) });
    setBone(h, 'chest', { x: -0.03 + 0.01 * sin(t * 1.2) });

    // Arms: bring down from T-pose to relaxed A-pose + subtle sway
    // Safe — arms are not in the head→hair spring bone chain
    setBone(h, 'leftUpperArm', { z: -0.8 + 0.03 * sin(t * 0.9) });
    setBone(h, 'rightUpperArm', { z: 0.8 - 0.03 * sin(t * 0.9) });
    setBone(h, 'leftLowerArm', { z: -0.15 + 0.02 * sin(t * 1.1) });
    setBone(h, 'rightLowerArm', { z: 0.15 - 0.02 * sin(t * 1.1) });
  }
}
