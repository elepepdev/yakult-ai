// ../../../../../tmp/opencode/w18.mjs
import * as THREE3 from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin } from "@pixiv/three-vrm";

// src/renderer/src/hooks/canvas/vrm/lib/VRMAnimationLoaderPlugin.ts
import * as THREE2 from "three";
import { VRMHumanBoneParentMap } from "@pixiv/three-vrm";

// src/renderer/src/hooks/canvas/vrm/lib/VRMAnimation.ts
import * as THREE from "three";
var VRMAnimation = class {
  duration;
  restHipsPosition;
  humanoidTracks;
  expressionTracks;
  lookAtTrack;
  constructor() {
    this.duration = 0;
    this.restHipsPosition = new THREE.Vector3();
    this.humanoidTracks = {
      translation: /* @__PURE__ */ new Map(),
      rotation: /* @__PURE__ */ new Map()
    };
    this.expressionTracks = /* @__PURE__ */ new Map();
    this.lookAtTrack = null;
  }
  createAnimationClip(vrm2) {
    const tracks = [];
    tracks.push(...this.createHumanoidTracks(vrm2));
    if (vrm2.expressionManager != null) {
      tracks.push(...this.createExpressionTracks(vrm2.expressionManager));
    }
    if (vrm2.lookAt != null) {
      const track = this.createLookAtTrack("lookAtTargetParent.quaternion");
      if (track != null) {
        tracks.push(track);
      }
    }
    return new THREE.AnimationClip("Clip", this.duration, tracks);
  }
  createHumanoidTracks(vrm2) {
    const humanoid = vrm2.humanoid;
    const metaVersion = vrm2.meta.metaVersion;
    const tracks = [];
    for (const [name, origTrack] of this.humanoidTracks.rotation.entries()) {
      const nodeName = humanoid.getNormalizedBoneNode(name)?.name;
      if (nodeName != null) {
        const newValues = [];
        const metaVersionZero = metaVersion === "0";
        let sign = metaVersionZero ? -1 : 1;
        let opposite = metaVersionZero ? 1 : 1;
        let prevQuaternion = new THREE.Quaternion();
        if (origTrack.values.length % 4 !== 0) {
          throw new Error("Invalid origTrack values length");
        }
        for (let i = 0; i < origTrack.values.length; i += 4) {
          const quaternion = new THREE.Quaternion(
            origTrack.values[i],
            origTrack.values[i + 1],
            origTrack.values[i + 2],
            origTrack.values[i + 3]
          );
          if (prevQuaternion.dot(quaternion) < 0 && metaVersionZero) {
            sign *= -1;
            opposite *= -1;
          }
          newValues.push(
            sign * origTrack.values[i],
            opposite * origTrack.values[i + 1],
            sign * origTrack.values[i + 2],
            opposite * origTrack.values[i + 3]
          );
          prevQuaternion = quaternion;
        }
        const track = origTrack.clone();
        track.values = new Float32Array(newValues);
        track.name = `${nodeName}.quaternion`;
        tracks.push(track);
      }
    }
    for (const [name, origTrack] of this.humanoidTracks.translation.entries()) {
      const nodeName = humanoid.getNormalizedBoneNode(name)?.name;
      if (nodeName != null) {
        const animationY = this.restHipsPosition.y;
        const humanoidY = humanoid.getNormalizedAbsolutePose().hips.position[1];
        const scale = humanoidY / animationY;
        const track = origTrack.clone();
        track.values = track.values.map(
          (v, i) => (metaVersion === "0" && i % 3 !== 1 ? -v : v) * scale
        );
        track.name = `${nodeName}.position`;
        tracks.push(track);
      }
    }
    return tracks;
  }
  createExpressionTracks(expressionManager) {
    const tracks = [];
    for (const [name, origTrack] of this.expressionTracks.entries()) {
      const trackName = expressionManager.getExpressionTrackName(name);
      if (trackName != null) {
        const track = origTrack.clone();
        track.name = trackName;
        tracks.push(track);
      }
    }
    return tracks;
  }
  createLookAtTrack(trackName) {
    if (this.lookAtTrack == null) {
      return null;
    }
    const track = this.lookAtTrack.clone();
    track.name = trackName;
    return track;
  }
};

// src/renderer/src/hooks/canvas/vrm/lib/utils/arrayChunk.ts
function arrayChunk(array, every) {
  const N = array.length;
  const ret = [];
  let current = [];
  let remaining = 0;
  for (let i = 0; i < N; i++) {
    const el = array[i];
    if (remaining <= 0) {
      remaining = every;
      current = [];
      ret.push(current);
    }
    current.push(el);
    remaining--;
  }
  return ret;
}

// src/renderer/src/hooks/canvas/vrm/lib/VRMAnimationLoaderPlugin.ts
var MAT4_IDENTITY = new THREE2.Matrix4();
var _v3A = new THREE2.Vector3();
var _quatA = new THREE2.Quaternion();
var _quatB = new THREE2.Quaternion();
var _quatC = new THREE2.Quaternion();
var VRMAnimationLoaderPlugin = class {
  parser;
  constructor(parser, options) {
    this.parser = parser;
  }
  get name() {
    return "VRMC_vrm_animation";
  }
  async afterRoot(gltf2) {
    const defGltf = gltf2.parser.json;
    const defExtensionsUsed = defGltf.extensionsUsed;
    if (defExtensionsUsed == null || defExtensionsUsed.indexOf(this.name) == -1) {
      return;
    }
    const defExtension = defGltf.extensions?.[this.name];
    if (defExtension == null) {
      return;
    }
    const nodeMap = this._createNodeMap(defExtension);
    const worldMatrixMap = await this._createBoneWorldMatrixMap(
      gltf2,
      defExtension
    );
    const hipsNode = defExtension.humanoid.humanBones["hips"].node;
    const hips = await gltf2.parser.getDependency(
      "node",
      hipsNode
    );
    const restHipsPosition = hips.getWorldPosition(new THREE2.Vector3());
    const clips = gltf2.animations;
    const animations = clips.map((clip, iAnimation) => {
      const defAnimation = defGltf.animations[iAnimation];
      const animation = this._parseAnimation(
        clip,
        defAnimation,
        nodeMap,
        worldMatrixMap
      );
      animation.restHipsPosition = restHipsPosition;
      return animation;
    });
    gltf2.userData.vrmAnimations = animations;
  }
  _createNodeMap(defExtension) {
    const humanoidIndexToName = /* @__PURE__ */ new Map();
    const expressionsIndexToName = /* @__PURE__ */ new Map();
    let lookAtIndex;
    const humanBones = defExtension.humanoid?.humanBones;
    if (humanBones) {
      Object.entries(humanBones).forEach(([name, bone]) => {
        const { node } = bone;
        humanoidIndexToName.set(node, name);
      });
    }
    const preset = defExtension.expressions?.preset;
    if (preset) {
      Object.entries(preset).forEach(([name, expression]) => {
        const { node } = expression;
        expressionsIndexToName.set(node, name);
      });
    }
    const custom = defExtension.expressions?.custom;
    if (custom) {
      Object.entries(custom).forEach(([name, expression]) => {
        const { node } = expression;
        expressionsIndexToName.set(node, name);
      });
    }
    lookAtIndex = defExtension.lookAt?.node ?? null;
    return { humanoidIndexToName, expressionsIndexToName, lookAtIndex };
  }
  async _createBoneWorldMatrixMap(gltf2, defExtension) {
    gltf2.scene.updateWorldMatrix(false, true);
    const threeNodes = await gltf2.parser.getDependencies(
      "node"
    );
    const worldMatrixMap = /* @__PURE__ */ new Map();
    for (const [boneName, { node }] of Object.entries(
      defExtension.humanoid.humanBones
    )) {
      const threeNode = threeNodes[node];
      worldMatrixMap.set(boneName, threeNode.matrixWorld);
      if (boneName === "hips") {
        worldMatrixMap.set(
          "hipsParent",
          threeNode.parent?.matrixWorld ?? MAT4_IDENTITY
        );
      }
    }
    return worldMatrixMap;
  }
  _parseAnimation(animationClip, defAnimation, nodeMap, worldMatrixMap) {
    const tracks = animationClip.tracks;
    const defChannels = defAnimation.channels;
    const result = new VRMAnimation();
    result.duration = animationClip.duration;
    defChannels.forEach((channel, iChannel) => {
      const { node, path } = channel.target;
      const origTrack = tracks[iChannel];
      if (node == null) {
        return;
      }
      const boneName = nodeMap.humanoidIndexToName.get(node);
      if (boneName != null) {
        let parentBoneName = VRMHumanBoneParentMap[boneName];
        while (parentBoneName != null && worldMatrixMap.get(parentBoneName) == null) {
          parentBoneName = VRMHumanBoneParentMap[parentBoneName];
        }
        parentBoneName ??= "hipsParent";
        if (path === "translation") {
          const hipsParentWorldMatrix = worldMatrixMap.get("hipsParent");
          const trackValues = arrayChunk(origTrack.values, 3).flatMap(
            (v) => _v3A.fromArray(v).applyMatrix4(hipsParentWorldMatrix).toArray()
          );
          const track = origTrack.clone();
          track.values = new Float32Array(trackValues);
          result.humanoidTracks.translation.set(boneName, track);
        } else if (path === "rotation") {
          const worldMatrix = worldMatrixMap.get(boneName);
          const parentWorldMatrix = worldMatrixMap.get(parentBoneName);
          _quatA.setFromRotationMatrix(worldMatrix).normalize().invert();
          _quatB.setFromRotationMatrix(parentWorldMatrix).normalize();
          const trackValues = arrayChunk(origTrack.values, 4).flatMap(
            (q) => _quatC.fromArray(q).premultiply(_quatB).multiply(_quatA).toArray()
          );
          const track = origTrack.clone();
          track.values = new Float32Array(trackValues);
          result.humanoidTracks.rotation.set(boneName, track);
        } else {
          throw new Error(`Invalid path "${path}"`);
        }
        return;
      }
      const expressionName = nodeMap.expressionsIndexToName.get(node);
      if (expressionName != null) {
        if (path === "translation") {
          const times = origTrack.times;
          const values = new Float32Array(origTrack.values.length / 3);
          for (let i = 0; i < values.length; i++) {
            values[i] = origTrack.values[3 * i];
          }
          const newTrack = new THREE2.NumberKeyframeTrack(
            `${expressionName}.weight`,
            times,
            values
          );
          result.expressionTracks.set(expressionName, newTrack);
        } else {
          throw new Error(`Invalid path "${path}"`);
        }
        return;
      }
      if (node === nodeMap.lookAtIndex) {
        if (path === "rotation") {
          result.lookAtTrack = origTrack;
        } else {
          throw new Error(`Invalid path "${path}"`);
        }
      }
    });
    return result;
  }
};

// ../../../../../tmp/opencode/w18.mjs
globalThis.self = globalThis;
var fs = await import("node:fs/promises");
var modelBuf = await fs.readFile("/home/fatih/Projects/yakult-mybini/vrm-models/Yakult.vrm");
var loader = new GLTFLoader();
loader.register((p) => new VRMLoaderPlugin(p, { autoUpdateHumanoid: true }));
var gltf = await loader.parseAsync(modelBuf.buffer, "http://localhost/models/");
var vrm = gltf.userData.vrm;
vrm.update(0.016);
async function loadAnim(path) {
  const buf = await fs.readFile(path);
  const l = new GLTFLoader();
  l.register((p) => new VRMAnimationLoaderPlugin(p));
  const g = await l.parseAsync(buf.buffer, "http://localhost/");
  return g.userData.vrmAnimations[0];
}
var idleAnim = await loadAnim("/home/fatih/Projects/yakult-mybini/deskcom/src/renderer/public/animations/idle_loop.vrma");
var idleClip = idleAnim.createAnimationClip(vrm);
var mixer = new THREE3.AnimationMixer(vrm.scene);
var action = mixer.clipAction(idleClip);
action.setEffectiveWeight(1);
action.play();
var B = {
  LH: vrm.humanoid.getNormalizedBoneNode("leftHand"),
  RH: vrm.humanoid.getNormalizedBoneNode("rightHand"),
  LU: vrm.humanoid.getNormalizedBoneNode("leftUpperArm"),
  RU: vrm.humanoid.getNormalizedBoneNode("rightUpperArm"),
  LS: vrm.humanoid.getNormalizedBoneNode("leftShoulder"),
  RS: vrm.humanoid.getNormalizedBoneNode("rightShoulder"),
  LL: vrm.humanoid.getNormalizedBoneNode("leftLowerArm"),
  RL: vrm.humanoid.getNormalizedBoneNode("rightLowerArm"),
  chest: vrm.humanoid.getNormalizedBoneNode("chest")
};
var dt = 1 / 60;
var E = new THREE3.Euler();
var Q = new THREE3.Quaternion();
function mirrorW(q) {
  const M = new THREE3.Matrix4().makeScale(-1, 1, 1);
  const qM = new THREE3.Matrix4().makeRotationFromQuaternion(q);
  const P = new THREE3.Matrix4().multiplyMatrices(M, qM).multiply(M);
  return new THREE3.Quaternion().setFromRotationMatrix(P);
}
mixer.setTime(0);
mixer.update(0);
var leftBase = null;
for (let f = 0; f < 1.5 / dt; f++) {
  mixer.update(dt);
  if (!leftBase) leftBase = B.LU.quaternion.clone();
  const spread = 0.1 + Math.sin(f * dt * Math.PI * 2 / 8) * 0.075;
  E.set(0, 0, spread);
  Q.setFromEuler(E);
  B.LU.quaternion.copy(leftBase).multiply(Q);
  vrm.scene.updateMatrixWorld(true);
  const set = (pR, pL, qL, bone) => {
    const wQ = new THREE3.Quaternion().multiplyQuaternions(pL.getWorldQuaternion(new THREE3.Quaternion()), qL);
    bone.quaternion.copy(pR.getWorldQuaternion(new THREE3.Quaternion()).invert().multiply(mirrorW(wQ)));
    vrm.scene.updateMatrixWorld(true);
  };
  set(B.chest, B.chest, B.LS.quaternion, B.RS);
  set(B.RS, B.LS, B.LU.quaternion, B.RU);
  set(B.RU, B.LU, B.LL.quaternion, B.RL);
  set(B.RL, B.LL, B.LH.quaternion, B.RH);
  vrm.update(dt);
  vrm.scene.updateMatrixWorld(true);
}
var wp = (b) => {
  const v = b.getWorldPosition(new THREE3.Vector3());
  return `(${v.x.toFixed(3)},${v.y.toFixed(3)},${v.z.toFixed(3)})`;
};
var wq = (b) => {
  const q = b.getWorldQuaternion(new THREE3.Quaternion());
  return `x=${q.x.toFixed(3)} y=${q.y.toFixed(3)} z=${q.z.toFixed(3)} w=${q.w.toFixed(3)}`;
};
console.log("LS pos", wp(B.LS), "  RS pos", wp(B.RS));
console.log("LU pos", wp(B.LU), "  RU pos", wp(B.RU));
console.log("LH pos", wp(B.LH), "  RH pos", wp(B.RH));
console.log("mirror of LH about x=-0.131 (mid-shoulder):", wp({ getWorldPosition: () => new THREE3.Vector3(2 * -0.131 - B.LH.getWorldPosition(new THREE3.Vector3()).x, B.LH.getWorldPosition(new THREE3.Vector3()).y, B.LH.getWorldPosition(new THREE3.Vector3()).z) }));
console.log("LH wq ", wq(B.LH));
console.log("RH wq ", wq(B.RH));
var m = mirrorW(B.LH.getWorldQuaternion(new THREE3.Quaternion()));
console.log("mirror(LH) wq", `x=${m.x.toFixed(3)} y=${m.y.toFixed(3)} z=${m.z.toFixed(3)} w=${m.w.toFixed(3)}`);
