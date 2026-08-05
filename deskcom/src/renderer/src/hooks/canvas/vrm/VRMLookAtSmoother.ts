// @ts-nocheck
import type { VRM } from '@pixiv/three-vrm';
import * as THREE from 'three';

export function setupLookAt(vrm: VRM, camera: THREE.Object3D): THREE.Object3D | null {
  if (!vrm.lookAt) return null;

  const lookAtTarget = new THREE.Object3D();
  camera.add(lookAtTarget);
  vrm.lookAt.target = lookAtTarget;
  return lookAtTarget;
}
