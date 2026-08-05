/* eslint-disable no-underscore-dangle */
/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRM, VRMLoaderPlugin, MToonMaterialLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { ModelInfo } from '@/context/live2d-config-context';
import { AutoBlink } from './vrm/AutoBlink';
import { setupLookAt } from './vrm/VRMLookAtSmoother';
import { ProceduralAnimation } from './vrm/ProceduralAnimation';
import { loadVRMAnimation } from './vrm/lib/loadVRMAnimation';
import { VRMAudioLipSync } from './vrm/VRMAudioLipSync';
import { VRMAnimation } from './vrm/lib/VRMAnimation';

interface UseVRMProps {
  modelInfo: ModelInfo | undefined;
  canvasRef: React.RefObject<HTMLCanvasElement>;
}

interface VRMState {
  isLoaded: boolean;
  currentExpression: string | null;
  isSpeaking: boolean;
}

const DEFAULT_VISEME_MAP = {
  aa: 'aa',
  ee: 'ee',
  ih: 'ih',
  oh: 'oh',
  ou: 'ou',
};

const DEFAULT_EXPRESSION_MAP = {
  neutral: 'neutral',
  joy: 'happy',
  anger: 'angry',
  sadness: 'sad',
  surprise: 'surprised',
  relaxed: 'relaxed',
};

// The model's `surprised` expression is a single morph (Face idx 5) that bakes
// wide eyes AND an open mouth together, with overrideMouth: none — there's no
// separate mouth morph to zero out. Capping its weight keeps the mouth from
// flaring open on its own; the `aa` viseme (lip-sync) then owns mouth opening.
// ponytail: single-morph cap, retune per model if the eyes look weak.
const EMOTION_EXPRESSION_WEIGHT_CAP: Record<string, number> = {
  surprised: 0.4,
};

// Temp objects for head-follow quaternion math (avoid per-frame allocations)
const HEAD_OFFSET_QUAT = new THREE.Quaternion();
const HEAD_OFFSET_EULER = new THREE.Euler(0, 0, 0, 'YXZ');
const EYE_OFFSET_QUAT = new THREE.Quaternion();
const EYE_OFFSET_EULER = new THREE.Euler(0, 0, 0, 'YXZ');

// Temp objects for idle arm-spread quaternion math (avoid per-frame allocations)
const ARM_OFFSET_QUAT = new THREE.Quaternion();
const ARM_OFFSET_EULER = new THREE.Euler(0, 0, 0, 'XYZ');
// Temp objects for mirroring the left arm chain onto the right (sagittal plane)
const ARM_MIRROR_WORLD_Q = new THREE.Quaternion();
const ARM_MIRROR_REFLECT_Q = new THREE.Quaternion();
const ARM_MIRROR_INV_Q = new THREE.Quaternion();

// Reflect `leftBone`'s world orientation (parented to `leftParentWQ`) onto
// `rightBone` (parented to `rightParentWQ`) across the vertical sagittal plane.
// This makes the right arm an exact mirror of the left, so both hands render at
// the same height and swing width regardless of the baked pose's asymmetry.
function mirrorArmBoneInto(
  leftParentWQ: THREE.Quaternion,
  rightParentWQ: THREE.Quaternion,
  leftBone: THREE.Object3D,
  rightBone: THREE.Object3D,
) {
  ARM_MIRROR_WORLD_Q.copy(leftParentWQ).multiply(leftBone.quaternion);
  // Reflection about the plane x=0 flips the rotation axis' y/z components.
  ARM_MIRROR_REFLECT_Q.set(
    ARM_MIRROR_WORLD_Q.x,
    -ARM_MIRROR_WORLD_Q.y,
    -ARM_MIRROR_WORLD_Q.z,
    ARM_MIRROR_WORLD_Q.w,
  );
  rightBone.quaternion
    .copy(ARM_MIRROR_INV_Q.copy(rightParentWQ).invert())
    .multiply(ARM_MIRROR_REFLECT_Q);
}



// The greeting peaks in a "surprised from below" pose around t≈2.5s: the head is
// pitched up ~14-16° while the body is still rising from the squat. We hold that
// exact frame at startup and begin the greeting from the same time so the wave
// follows continuously.
const STARTUP_SURPRISE_HOLD_TIME = 2.5;

/**
 * Build an animation clip that holds ONE frame of a VRMAnimation as a static
 * pose. Used to rest the character directly in the greeting's "surprised from
 * below" pose (head up, body mid-squat), so greeting playback flows from it
 * without a stand→squat→stand jump.
 *
 * @param holdTime seconds into the source animation to sample; 0 = first frame.
 */
function createStaticPoseClip(vrmAnimation: VRMAnimation, vrm: VRM, holdTime = 0): THREE.AnimationClip {
  const src = vrmAnimation.createAnimationClip(vrm);
  const duration = Math.max(src.duration, 0.016);
  const tracks = src.tracks.map((track) => {
    const size = track.getValueSize();
    let first: number[];
    if (holdTime > 0) {
      const result = new Float32Array(size);
      const interpolant = track.createInterpolant(result);
      interpolant.evaluate(holdTime);
      first = Array.from(result);
    } else {
      first = Array.from(track.values.slice(0, size));
    }
    const TrackClass = track.constructor as new (
      name: string,
      times: number[],
      values: number[],
    ) => THREE.KeyframeTrack;
    return new TrackClass(track.name, [0, duration], [...first, ...first]);
  });
  return new THREE.AnimationClip('SquatIdleHold', duration, tracks);
}

/**
 * Re-bake an animation clip's neck track so the head's world-up vector stays
 * exactly vertical on every keyframe. idle_loop.vrma bakes a small head tilt
 * ("dangak") spread across the whole spine chain (neck + chest + upperChest),
 * so zeroing the neck alone can't fix it. Instead, for each neck keyframe we
 * sample the full clip pose, measure the head's world-up deviation, and write a
 * neck correction that rotates it back onto +Y. Applied in the normalized-bone
 * space the clip already targets, so results stay valid through the mixer.
 */
function levelHeadToWorldUp(clip: THREE.AnimationClip, vrm: VRM): void {
  const humanoid = vrm.humanoid;
  if (!humanoid) return;
  const neckNode = humanoid.getNormalizedBoneNode('neck');
  const headNode = humanoid.getNormalizedBoneNode('head');
  const neckTrackName = neckNode ? `${neckNode.name}.quaternion` : null;
  const neckTrack = neckTrackName
    ? clip.tracks.find((t) => t.name === neckTrackName)
    : clip.tracks.find((t) => t.name.endsWith('neck.quaternion'));
  if (!neckTrack || !headNode || !neckNode) return;
  if (neckTrack.getValueSize() !== 4) return;

  // Map clip rotation tracks to their normalized bone nodes (all rest at identity).
  const nodeByName = new Map<string, THREE.Object3D>();
  vrm.scene.traverse((o) => nodeByName.set(o.name, o));

  const rotationTracks = clip.tracks.filter(
    (t) => t.getValueSize() === 4 && t.name.endsWith('.quaternion'),
  );
  const samplers = rotationTracks.map((track) => {
    const buf = new Float32Array(4);
    return { node: nodeByName.get(track.name.replace('.quaternion', '')), ip: track.createInterpolant(buf), buf };
  }).filter((s) => s.node != null);

  const values = neckTrack.values as Float32Array;
  const times = neckTrack.times as ArrayLike<number>;
  const n = times.length;

  // Snapshot bone quaternions so we can restore the scene after baking.
  const snapshot = new Map<THREE.Object3D, THREE.Quaternion>();
  for (const s of samplers) snapshot.set(s.node, s.node.quaternion.clone());

  const up = new THREE.Vector3();
  const axis = new THREE.Vector3();
  const worldUp = new THREE.Vector3(0, 1, 0);
  const corr = new THREE.Quaternion();
  const neckLocalCorr = new THREE.Quaternion();
  const parentWorld = new THREE.Quaternion();
  const headWorld = new THREE.Quaternion();

  for (let i = 0; i < n; i++) {
    const t = times[i];
    for (const s of samplers) {
      s.ip.evaluate(t);
      s.node.quaternion.fromArray(s.buf);
    }
    vrm.scene.updateMatrixWorld(true);

    up.set(0, 1, 0).applyQuaternion(headNode.getWorldQuaternion(headWorld));
    const a = up.clone().normalize();
    const dot = Math.min(1, Math.max(-1, a.dot(worldUp)));
    axis.crossVectors(a, worldUp);
    if (axis.lengthSq() < 1e-8) {
      corr.identity();
    } else {
      corr.setFromAxisAngle(axis.normalize(), Math.acos(dot));
    }

    // Convert the world-space correction into the neck's local frame.
    const parent = neckNode.parent;
    if (parent) {
      parentWorld.copy(parent.getWorldQuaternion(new THREE.Quaternion()));
      neckLocalCorr.copy(parentWorld).invert().multiply(corr).multiply(parentWorld);
    } else {
      neckLocalCorr.copy(corr);
    }

    const orig = new THREE.Quaternion(values[i * 4], values[i * 4 + 1], values[i * 4 + 2], values[i * 4 + 3]);
    const corrected = neckLocalCorr.multiply(orig);
    values[i * 4] = corrected.x;
    values[i * 4 + 1] = corrected.y;
    values[i * 4 + 2] = corrected.z;
    values[i * 4 + 3] = corrected.w;
  }

  for (const [node, q] of snapshot) node.quaternion.copy(q);
}

/**
 * Move camera along the look direction to simulate zoom.
 * scale=1 → base distance, scale=0.5 → 2x farther (smaller), scale=2 → half distance (bigger).
 * The model stays at scale=1 so the spring bone solver is unaffected.
 */
function applyCameraZoom(
  camera: THREE.PerspectiveCamera,
  basePos: THREE.Vector3,
  lookAt: THREE.Vector3,
  scale: number,
) {
  const dir = new THREE.Vector3().subVectors(basePos, lookAt);
  const baseDistance = dir.length();
  const s = Math.max(0.1, Math.min(5.0, scale));
  const newDistance = baseDistance / s;
  dir.normalize().multiplyScalar(newDistance);
  camera.position.copy(lookAt).add(dir);
  camera.lookAt(lookAt);
}

const SMOOTH_FACTOR = 0.15;

export function useVRM({ modelInfo, canvasRef }: UseVRMProps) {
  const [state, setState] = useState<VRMState>({
    isLoaded: false,
    currentExpression: null,
    isSpeaking: false,
  });

  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const clockRef = useRef<THREE.Clock>(new THREE.Clock());
  const animationIdRef = useRef<number>(0);
  const prevModelUrlRef = useRef<string | null>(null);

  // Scale state for scroll-to-resize (camera distance zoom, NOT model scale)
  const currentScaleRef = useRef<number>(modelInfo?.kScale || 1.0);
  const targetScaleRef = useRef<number>(modelInfo?.kScale || 1.0);
  // Camera base position and lookAt target (set after model loads)
  const baseCameraPosRef = useRef<THREE.Vector3 | null>(null);
  const cameraLookAtRef = useRef<THREE.Vector3 | null>(null);

  // Drag state
  const [isDragging, setIsDragging] = useState(false);
  const isDraggingRef = useRef(false);
  const dragStartScreenRef = useRef({ x: 0, y: 0 });
  const dragStartModelRef = useRef({ x: 0, y: 0, z: 0 });

  // Cursor-follow head tracking (subtle)
  const lookAtTargetRef = useRef<THREE.Object3D | null>(null);
  const cursorPosRef = useRef({ x: 0, y: 0 });
  const cursorSmoothedRef = useRef({ x: 0, y: 0 });
  const headBoneRef = useRef<THREE.Object3D | null>(null);
  const headBaseQuatRef = useRef<THREE.Quaternion | null>(null);
  const leftEyeBoneRef = useRef<THREE.Object3D | null>(null);
  const rightEyeBoneRef = useRef<THREE.Object3D | null>(null);

  // Expression smoothing — target weights that the animation loop lerps toward
  const expressionTargetsRef = useRef<Record<string, number>>({});

  // Viseme (lip-sync) — applied directly every frame for responsiveness
  const visemeActiveRef = useRef<Record<string, number>>({});
  // Track which viseme shapes exist on the model (cached after load)
  const visemeShapeNamesRef = useRef<string[]>([]);

  // AutoBlink instance
  const autoBlinkRef = useRef<AutoBlink | null>(null);
  // ProceduralAnimation instance
  const proceduralAnimRef = useRef<ProceduralAnimation | null>(null);
  // AnimationMixer for idle animation playback
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  // Idle animation action (home state — always restored after one-shot animations)
  const idleActionRef = useRef<THREE.AnimationAction | null>(null);
  // Start-pose action: a static hold of the greeting's first frame (squat/jongkok)
  // that the character appears in before the startup greeting plays
  const squatHoldActionRef = useRef<THREE.AnimationAction | null>(null);
  // Currently playing non-idle action (greeting, etc.)
  const currentActionRef = useRef<THREE.AnimationAction | null>(null);
  // Monotonic, clamped time for the idle arm-spread sine. Deliberately NOT the
  // clock's elapsedTime: getDelta() returns the whole hidden duration after a
  // tab refocus, teleporting elapsedTime forward and snapping the sine phase to
  // an arbitrary angle (a sudden arm swing).
  const armSpreadTimeRef = useRef(0);
  // Base quaternions for the idle arm-spread. The idle clip's upper-arm track is
  // essentially static, so the mixer's accumulator change-detection skips writing
  // the arm bones on most frames — a naive `multiply()` of the spread offset onto
  // the live bone then COMPOUNDS frame-over-frame (the arms sweep far past the
  // intended angle and snap back whenever the mixer finally writes, e.g. at each
  // loop wrap). Compose the offset absolutely from a base captured once when idle
  // takes over, like the head-follow block does.
  const armLeftBaseQuatRef = useRef<THREE.Quaternion | null>(null);
  // Ramps the spread in over ~0.5s whenever idle (re)takes over, so the offset
  // doesn't pop in at full strength right after a crossfade.
  const armSpreadRampRef = useRef(0);
  // Track current emotion for lip-sync weight adjustment
  const currentEmotionRef = useRef<string>('neutral');
  // Audio lip-sync engine
  const lipSyncRef = useRef<VRMAudioLipSync>(new VRMAudioLipSync());
  const lipSyncAudioRef = useRef<HTMLAudioElement | null>(null);

  // Get viseme map from model info or defaults
  const getVisemeMap = useCallback(() => {
    return { ...DEFAULT_VISEME_MAP, ...(modelInfo?.visemeMap || {}) };
  }, [modelInfo?.visemeMap]);

  // Get emotion map from model info or defaults
  const getEmotionMap = useCallback(() => {
    return { ...DEFAULT_EXPRESSION_MAP, ...(modelInfo?.emotionMap || {}) };
  }, [modelInfo?.emotionMap]);

  /**
   * Initialize Three.js scene
   */
  const initScene = useCallback(() => {
    console.log('[useVRM] initScene called');
    if (!canvasRef.current) {
      console.warn('[useVRM] canvasRef.current is null');
      return;
    }

    const canvas = canvasRef.current;
    const parent = canvas.parentElement;
    if (!parent) {
      console.warn('[useVRM] canvas parentElement is null');
      return;
    }

    const width = parent.clientWidth || 300;
    const height = parent.clientHeight || 400;
    console.log('[useVRM] canvas dimensions:', width, 'x', height);

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera — portrait-style, eye-level, directly in front (no downward angle)
    const camera = new THREE.PerspectiveCamera(20, width / height, 0.1, 100);
    camera.position.set(0, 1.4, 3.0);
    camera.lookAt(0, 1.4, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.setClearColor(0x000000, 0); // Transparent background
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    rendererRef.current = renderer;

    // Lights — brighter ambient like amica
    const ambientLight = new THREE.AmbientLight(0xffffff, 2.0);
    scene.add(ambientLight);

    const mainLight = new THREE.DirectionalLight(0xffffff, 0.6);
    mainLight.position.set(1.0, 1.0, 1.0).normalize();
    scene.add(mainLight);

    console.log('[useVRM] scene initialized successfully');
  }, [canvasRef]);

  /**
   * Load VRM model from URL
   */
  const loadVRM = useCallback(async (url: string) => {
    console.log('[useVRM] loadVRM called with URL:', url);
    if (!sceneRef.current || !rendererRef.current) {
      console.warn('[useVRM] scene or renderer not initialized');
      return;
    }

    // Remove previous model with proper cleanup
    if (vrmRef.current) {
      console.log('[useVRM] removing previous VRM model');
      try { VRMUtils.deepDispose(vrmRef.current.scene); } catch { /* ok */ }
      sceneRef.current.remove(vrmRef.current.scene);
      vrmRef.current = null;
    }
    autoBlinkRef.current = null;
    proceduralAnimRef.current = null;
    if (mixerRef.current) {
      mixerRef.current.stopAllAction();
      mixerRef.current = null;
    }

    try {
      console.log('[useVRM] creating GLTFLoader and registering plugins');
      const loader = new GLTFLoader();
      loader.register((parser) => new VRMLoaderPlugin(parser, {
        mtoonMaterialPlugin: new MToonMaterialLoaderPlugin(parser),
      }));

      console.log('[useVRM] starting loadAsync for:', url);
      const gltf = await loader.loadAsync(url);
      console.log('[useVRM] loadAsync completed, gltf keys:', Object.keys(gltf));

      const vrm = gltf.userData.vrm as VRM;
      console.log('[useVRM] vrm from gltf.userData:', vrm ? 'found' : 'NOT FOUND');

      if (!vrm) {
        console.error('[useVRM] Failed to load VRM: no vrm data in gltf');
        return;
      }

      // Optimize VRM geometry
      VRMUtils.removeUnnecessaryVertices(gltf.scene);
      VRMUtils.removeUnnecessaryJoints(gltf.scene);

      // Enhance texture quality for sharper rendering
      const maxAnisotropy = rendererRef.current?.capabilities.getMaxAnisotropy() || 16;
      gltf.scene.traverse((obj: any) => {
        obj.frustumCulled = false;
        if (!obj.isMesh) return;
        const materials = Array.isArray(obj.material) ? obj.material : [obj.material];
        for (const mat of materials) {
          if (!mat) continue;
          // Improve all texture slots
          const textureKeys = ['map', 'normalMap', 'emissiveMap', 'occlusionMap', 'metalnessMap', 'roughnessMap'];
          for (const key of textureKeys) {
            const tex = mat[key];
            if (tex && tex.image) {
              tex.magFilter = THREE.LinearFilter;
              tex.minFilter = THREE.LinearMipMapLinearFilter;
              tex.anisotropy = maxAnisotropy;
              tex.generateMipmaps = true;
              tex.needsUpdate = true;
            }
          }
        }
      });

      vrmRef.current = vrm;
      sceneRef.current.add(vrm.scene);

      // VRM 0.x rotation fix (amica model.ts:211-213)
      if (vrm.meta?.metaVersion === '0') {
        vrm.scene.rotation.y = Math.PI;
      }

      // Model position — VRM already faces -Z (toward camera) after loader correction
      vrm.scene.position.set(0, 0, 0);
      // NOTE: Do NOT apply scale to vrm.scene.scale — spring bone solver in three-vrm
      // v3.5.5 doesn't handle runtime scale changes. Use camera distance for zoom instead.
      vrm.scene.scale.set(1, 1, 1);

      // Cache available expression names
      expressionTargetsRef.current = {};
      visemeActiveRef.current = {};
      currentEmotionRef.current = 'neutral';

      // Caching viseme shape names
      const visemeMap = getVisemeMap();
      const expMap = vrm.expressionManager?.expressionMap;
      visemeShapeNamesRef.current = [];
      if (expMap) {
        for (const visemeName of Object.values(visemeMap)) {
          if (visemeName in expMap) {
            visemeShapeNamesRef.current.push(visemeName);
          }
        }
      }
      console.log('[useVRM] viseme shape names:', visemeShapeNamesRef.current);

      // Set neutral expression by default
      if ('neutral' in (vrm.expressionManager?.expressionMap || {})) {
        expressionTargetsRef.current['neutral'] = 1.0;
      }

      // Initialize AutoBlink
      if (vrm.expressionManager) {
        autoBlinkRef.current = new AutoBlink(vrm.expressionManager);
      }

      // Initialize ProceduralAnimation (fallback if no animation file)
      proceduralAnimRef.current = new ProceduralAnimation(vrm);

      // Initialize LookAt (eyes track camera)
      if (cameraRef.current) {
        lookAtTargetRef.current = setupLookAt(vrm, cameraRef.current);
      }

      // Capture head bone for cursor-follow head tracking
      if (vrm.humanoid) {
        headBoneRef.current = vrm.humanoid.getNormalizedBoneNode('head') || null;
        leftEyeBoneRef.current = vrm.humanoid.getRawBoneNode('leftEye') || null;
        rightEyeBoneRef.current = vrm.humanoid.getRawBoneNode('rightEye') || null;
      }

      // Reset clock so delta starts small (prevents spring bone explosion)
      clockRef.current = new THREE.Clock();
      clockRef.current.start();

      // Load idle animation (.vrma) — gives model proper resting pose + spring bone init.
      // Home state is the STANDING idle loop (idle_loop.vrma). We start it at weight 0
      // and instead play a static HOLD of greeting.vrma's first frame (the squat /
      // jongkok) at weight 1, so the character appears directly in the squat. The
      // startup greeting then plays from that squat and the standing idle takes over.
      let hasIdleAnimation = false;
      try {
        const vrmAnimation = await loadVRMAnimation('/animations/idle_loop.vrma');
        if (vrmAnimation) {
          const mixer = new THREE.AnimationMixer(vrm.scene);
          const clip = vrmAnimation.createAnimationClip(vrm);
          const action = mixer.clipAction(clip);
          action.setEffectiveWeight(0);
          action.play();
          mixerRef.current = mixer;
          idleActionRef.current = action;
          hasIdleAnimation = true;

          // Start pose: static hold of the greeting's "surprised from below"
          // frame (t≈2.5s — head up, body mid-squat). Played at weight 1 while
          // the standing idle is muted, so the character appears surprised from
          // below before the greeting plays.
          const greetingAnim = await loadVRMAnimation('/animations/greeting.vrma');
          if (greetingAnim) {
            // idle_loop.vrma bakes a small head tilt ("dangak") across the whole
            // spine chain. Re-bake its neck track so the head's world-up stays
            // exactly vertical on every keyframe — the idle head sits perfectly
            // level, straight.
            levelHeadToWorldUp(clip, vrm);
            console.log('[useVRM] idle head levelled to world-up (straight, no dangak)');

            const squatClip = createStaticPoseClip(greetingAnim, vrm, STARTUP_SURPRISE_HOLD_TIME);
            const squatAction = mixer.clipAction(squatClip);
            squatAction.setEffectiveWeight(1);
            squatAction.play();
            squatHoldActionRef.current = squatAction;
            console.log('[useVRM] idle (standing) + surprise start pose loaded, clip duration:', clip.duration);
          } else {
            console.warn('[useVRM] failed to load greeting for squat start pose');
          }
        } else {
          console.warn('[useVRM] loadVRMAnimation returned null');
        }
      } catch (animErr) {
        console.warn('[useVRM] failed to load idle animation, using procedural fallback:', animErr);
      }

      // Greeting is loaded on-demand in playVRMA() — no preload needed since we
      // no longer auto-play it at startup.

      // If no idle animation, use procedural pose as fallback
      if (!hasIdleAnimation && proceduralAnimRef.current) {
        proceduralAnimRef.current.update(0);
      }

      // CRITICAL: mixer.update(0) applies first animation frame to bones,
      // THEN vrm.update(0) initializes spring bones with the correct pose
      // (amica viewer.ts:741: this.model.update(0) calls mixer.update(0) then vrm.update(0))
      if (mixerRef.current) {
        mixerRef.current.update(0);
        console.log('[useVRM] mixer.update(0) called — animation applied to bones');
        // Force world matrix update so spring bone solver reads fresh parent transforms
        vrm.scene.updateMatrixWorld(true);
      }

      // Capture head bone's base (rest/idle) quaternion ONCE, after the idle pose
      // is applied. Each frame we compute head = base × offset — an absolute value —
      // so the rotation never compounds across frames.
      // NOTE: the idle clip has NO head track, and levelHeadToWorldUp() levels the
      // head through the neck — so the cursor-follow base is IDENTITY. We must NOT
      // read the live head quaternion here: at this point the surprise squat-hold
      // (weight 1) is applied, so it would capture the head-up surprise pose and
      // pin the head ndangak/tilted even at center cursor.
      if (headBoneRef.current) {
        headBaseQuatRef.current = new THREE.Quaternion();
      }

      // No fixed eye base is captured: the baked eyeballs are aimed by the VRM
      // lookAt system each frame, and eye-follow composes its cursor offset on top
      // of that fresh pose (see the eye-follow block in the animation loop).

      // --- Spring bone diagnostics ---
      const sbManager = (vrm as any).springBoneManager;
      if (sbManager) {
        // joints is a Set in v3.5.5
        const jointsSet = sbManager.joints;
        const jointsCount = jointsSet ? (jointsSet.size ?? (Array.isArray(jointsSet) ? jointsSet.length : 0)) : 0;
        const colliders = sbManager.colliders || [];
        const colliderGroups = sbManager.colliderGroups || [];
        console.log(`[useVRM] SpringBoneManager found: ${jointsCount} joints, ${colliders.length} colliders, ${colliderGroups.length} collider groups`);
        if (jointsCount > 0) {
          const jointsArr = Array.from(jointsSet);
          // Log ALL joint bone names so we can identify hair joints
          const allBoneNames = jointsArr.map((j: any) => (j.bone || j._bone)?.name || '?');
          console.log(`[useVRM] ALL joint bones (${jointsCount}):`, allBoneNames.join(', '));
          // Log hair-specific joints in detail
          for (let i = 0; i < jointsArr.length; i++) {
            const j = jointsArr[i];
            const bone = j.bone || j._bone;
            const boneName = bone?.name || 'unknown';
            // Find hair joints by common naming patterns
            if (boneName.toLowerCase().includes('hair') || boneName.toLowerCase().includes('front') || boneName.toLowerCase().includes('side') || boneName.toLowerCase().includes('back')) {
              const settings = j.settings || j._settings || {};
              const child = j.child || j._child;
              const initChildPos = j.initialLocalChildPosition || j._initialLocalChildPosition;
              console.log(`[useVRM]   HAIR joint[${i}] bone=${boneName} child=${child?.name || 'null'} stiffness=${settings.stiffness ?? 'N/A'} dragForce=${settings.dragForce ?? 'N/A'} gravityPower=${settings.gravityPower ?? 'N/A'} gravityDir=${settings.gravityDir ? `(${settings.gravityDir.x?.toFixed(2)},${settings.gravityDir.y?.toFixed(2)},${settings.gravityDir.z?.toFixed(2)})` : 'N/A'} initChildPos=${initChildPos ? `(${initChildPos.x?.toFixed(4)},${initChildPos.y?.toFixed(4)},${initChildPos.z?.toFixed(4)})` : 'N/A'}`);
            }
          }
          // Also log first 3 joints in detail as reference
          for (let i = 0; i < Math.min(3, jointsArr.length); i++) {
            const j = jointsArr[i];
            const settings = j.settings || j._settings || {};
            const bone = j.bone || j._bone;
            const child = j.child || j._child;
            console.log(`[useVRM]   joint[${i}] bone=${bone?.name || 'unknown'} child=${child?.name || 'null'} stiffness=${settings.stiffness} dragForce=${settings.dragForce} gravityPower=${settings.gravityPower}`);
          }
        } else {
          console.warn('[useVRM] NO spring bone joints found — model may not have spring bones');
        }
        // Log collider details
        if (colliders.length > 0) {
          for (let i = 0; i < Math.min(3, colliders.length); i++) {
            const c = colliders[i];
            const shape = c.shape;
            console.log(`[useVRM]   collider[${i}] shape=${shape?.type || 'unknown'} radius=${shape?.radius ?? 'N/A'}`);
          }
        }
      } else {
        console.warn('[useVRM] No springBoneManager on VRM instance');
      }

      // Log VRM meta info
      console.log('[useVRM] VRM meta:', {
        version: vrm.meta?.metaVersion,
        name: vrm.meta?.name,
        specVersion: vrm.meta?.specVersion,
        hasExpressionManager: !!vrm.expressionManager,
        hasLookAt: !!vrm.lookAt,
        hasHumanoid: !!vrm.humanoid,
      });

      vrm.update(0);
      console.log('[useVRM] vrm.update(0) called — spring bones initialized');

      // Re-log spring bone state after update(0)
      if (sbManager) {
        const jointsAfter = sbManager.joints;
        const countAfter = jointsAfter ? (jointsAfter.size ?? (Array.isArray(jointsAfter) ? jointsAfter.length : 0)) : 0;
        console.log(`[useVRM] After vrm.update(0): ${countAfter} joints still present`);
        if (countAfter > 0) {
          const arr = Array.from(jointsAfter);
          const j0 = arr[0];
          const bone0 = j0.bone || j0._bone;
          const worldPos = bone0?.getWorldPosition(new THREE.Vector3());
          console.log(`[useVRM]   joint[0] bone=${bone0?.name} worldPos=${worldPos ? `(${worldPos.x.toFixed(3)}, ${worldPos.y.toFixed(3)}, ${worldPos.z.toFixed(3)})` : 'N/A'}`);
        }
      }

      // Reset camera to head bone position — eye level, directly in front
      if (vrm.humanoid && cameraRef.current) {
        const headNode = vrm.humanoid.getNormalizedBoneNode('head');
        if (headNode) {
          const headPos = headNode.getWorldPosition(new THREE.Vector3());
          // Camera at same X and Y as head, fixed Z distance in front
          cameraRef.current.position.set(headPos.x, headPos.y, 3.0);
          cameraRef.current.lookAt(headPos.x, headPos.y, headPos.z);
          // Store base camera state for zoom calculations
          baseCameraPosRef.current = cameraRef.current.position.clone();
          cameraLookAtRef.current = new THREE.Vector3(headPos.x, headPos.y, headPos.z);
          // Apply initial zoom via camera distance
          const initScale = modelInfo?.kScale || 1.0;
          currentScaleRef.current = initScale;
          targetScaleRef.current = initScale;
          applyCameraZoom(cameraRef.current, baseCameraPosRef.current, cameraLookAtRef.current, initScale);
        }
      }

      // Start animation loop
      if (animationIdRef.current) {
        console.log('[useVRM] cancelling existing animation loop');
        cancelAnimationFrame(animationIdRef.current);
      }
      console.log('[useVRM] starting animation loop');
      animate();

      // Auto-play the greeting animation once at startup: the character appears in
      // the squat start pose, greeting plays from that squat (jongkok → berdiri +
      // wave), then crossfades to the standing idle loop.
      setTimeout(() => {
        playStartupGreeting();
      }, 800);

      // --- Auto-discover VRM expressions for AI ---
      // Read all available expression names from the VRM model and send them
      // to the backend so it can auto-populate the emotion map for the AI prompt.
      const allExpressions = Object.keys(vrm.expressionManager?.expressionMap || {});
      // Filter out viseme and blink expressions (used for lip-sync / auto-blink, not emotions)
      const VISEME_NAMES = new Set(['aa', 'ee', 'ih', 'oh', 'ou']);
      const BLINK_NAMES = new Set(['blink', 'blinkLeft', 'blinkRight']);
      const emotionExpressions = allExpressions.filter(
        (name) => !VISEME_NAMES.has(name) && !BLINK_NAMES.has(name),
      );
      if (emotionExpressions.length > 0) {
        console.log('[useVRM] discovered emotion expressions:', emotionExpressions);
        window.dispatchEvent(new CustomEvent('vrm-expressions-discovered', {
          detail: { expressions: emotionExpressions },
        }));
      }

      setState(prev => ({ ...prev, isLoaded: true }));
      console.log('[useVRM] VRM model loaded successfully:', url);
    } catch (error) {
      console.error('[useVRM] Failed to load VRM model:', error);
      console.error('[useVRM] error details:', error instanceof Error ? error.message : String(error));
      if (error instanceof Error && error.stack) {
        console.error('[useVRM] error stack:', error.stack);
      }
    }
  }, [getVisemeMap, modelInfo?.kScale]);

  /**
   * Animation loop — applies expression & viseme weights with smoothing
   */
  const animate = useCallback(() => {
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) {
      console.warn('[useVRM] animate: missing refs, stopping loop');
      return;
    }

    const vrm = vrmRef.current;
    if (vrm && vrm.expressionManager) {
      const delta = Math.min(clockRef.current.getDelta(), 0.1);
      const exprManager = vrm.expressionManager;

      // --- Smooth camera zoom (scroll-to-resize) ---
      // Uses camera distance instead of model scale to avoid spring bone issues
      const clampedTarget = Math.max(0.1, Math.min(5.0, targetScaleRef.current));
      const currentScale = currentScaleRef.current;
      const diff = clampedTarget - currentScale;
      if (Math.abs(diff) > 0.001) {
        const newScale = currentScale + diff * 0.3;
        currentScaleRef.current = newScale;
        if (baseCameraPosRef.current && cameraLookAtRef.current && cameraRef.current) {
          applyCameraZoom(cameraRef.current, baseCameraPosRef.current, cameraLookAtRef.current, newScale);
        }
      }

      // --- AutoBlink ---
      if (autoBlinkRef.current) {
        autoBlinkRef.current.update(delta);
      }

      // --- Audio-driven lip-sync (per frame) ---
      const audio = lipSyncAudioRef.current;
      if (audio && !audio.paused && !audio.ended) {
        const lipSyncVolume = lipSyncRef.current.update(audio.currentTime);
        const visemeMap = getVisemeMap();
        // Primary viseme: aa (mouth open)
        const aaName = visemeMap['aa'] || 'aa';
        if (aaName in (exprManager.expressionMap || {})) {
          visemeActiveRef.current[aaName] = lipSyncVolume;
        }
        // Secondary visemes: distribute for natural mouth shaping. `aa` drives
        // the main open; oh/eh/ih/ou add subtler variation between syllables.
        const ehName = visemeMap['ee'] || 'ee';
        const ihName = visemeMap['ih'] || 'ih';
        const ohName = visemeMap['oh'] || 'oh';
        const ouName = visemeMap['ou'] || 'ou';
        if (ehName in (exprManager.expressionMap || {})) {
          visemeActiveRef.current[ehName] = lipSyncVolume * 0.45;
        }
        if (ihName in (exprManager.expressionMap || {})) {
          visemeActiveRef.current[ihName] = lipSyncVolume * 0.4;
        }
        if (ohName in (exprManager.expressionMap || {})) {
          visemeActiveRef.current[ohName] = lipSyncVolume * 0.6;
        }
        if (ouName in (exprManager.expressionMap || {})) {
          visemeActiveRef.current[ouName] = lipSyncVolume * 0.4;
        }
      } else if (!audio) {
        // No audio — clear viseme targets so decay takes over
        // (don't clear here if audio just ended; let the ended handler call stopLipSync)
      }

      // --- Smooth expressions (emotions) ---
      const allKeys = Object.keys(exprManager.expressionMap || {});

      for (const name of allKeys) {
        let target = expressionTargetsRef.current[name] ?? 0;
        // Cap emotion expressions whose baked morph flips the mouth open too
        // wide (e.g. surprised). Lip-sync `aa` still drives full mouth opening
        // while speaking via the viseme override above.
        const emotionCap = EMOTION_EXPRESSION_WEIGHT_CAP[name];
        if (emotionCap !== undefined) {
          target = Math.min(target, emotionCap);
        }
        const current = exprManager.getValue(name);
        // If a viseme is active for this shape, let viseme override — always at
        // full amplitude so the mouth opens clearly when speaking, regardless
        // of the current emotion.
        const visemeOverride = visemeActiveRef.current[name] ?? -1;
        if (visemeOverride >= 0) {
          exprManager.setValue(name, Math.min(1, visemeOverride));
        } else {
          // Normal expression smoothing
          const newWeight = current + (target - current) * SMOOTH_FACTOR;
          exprManager.setValue(name, Math.max(0, Math.min(1, newWeight)));
        }
      }

      // --- Viseme decay ---
      for (const name of visemeShapeNamesRef.current) {
        if (visemeActiveRef.current[name] === undefined || visemeActiveRef.current[name] < 0) {
          const current = exprManager.getValue(name);
          if (current > 0.01) {
            exprManager.setValue(name, current * 0.85);
          } else if (current > 0) {
            exprManager.setValue(name, 0);
          }
        }
      }

      // --- AnimationMixer (idle animation) — MUST run before vrm.update() ---
      if (mixerRef.current) {
        mixerRef.current.update(delta);
      }

      // --- Subtle idle arm spread ---
      // Adds a slow, gentle spreading of both arms outward from the standing idle
      // pose, then back. The baked idle rests ~20° from straight-down; the added
      // rotation peaks at +10° (0.175 rad) so the arms top out at ~30°. Composed
      // ABSOLUTELY from a base captured once when idle takes over (the idle clip's
      // upper-arm track is static, so the mixer skips writing the arm bones most
      // frames and a naive per-frame multiply would compound into a full
      // propeller spin). The right arm is then mirrored from the left (full
      // shoulder→upper→lower→hand chain) so both hands render at the same height
      // and swing width — the baked pose is asymmetric in world space, so equal
      // per-arm rotation on asymmetric rest poses reads as one hand spreading
      // wider than the other.
      const idleWeight = idleActionRef.current?.getEffectiveWeight() ?? 0;
      if (idleWeight > 0.95 && vrm.humanoid) {
        const leftArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
        if (leftArm) {
          if (armLeftBaseQuatRef.current === null) {
            armLeftBaseQuatRef.current = leftArm.quaternion.clone();
            armSpreadRampRef.current = 0;
          }
          // Advance the dedicated arm-spread clock with a clamped delta so the
          // sine phase never teleports (e.g. after tab refocus).
          armSpreadTimeRef.current += Math.min(delta, 0.1);
          armSpreadRampRef.current = Math.min(1, armSpreadRampRef.current + delta / 0.5);
          const ARM_SPREAD_PERIOD = 8.0; // seconds per full out-and-back cycle
          // Added rotation (rad): raise=0.10 ± amplitude=0.075 → 0.025..0.175.
          // With the ~20° baked rest that is ~21°..30° from straight-down.
          const ARM_SPREAD_RAISE = 0.10;
          const ARM_SPREAD_AMPLITUDE = 0.075;
          const armSpread = (
            ARM_SPREAD_RAISE + Math.sin(
              (armSpreadTimeRef.current * Math.PI * 2) / ARM_SPREAD_PERIOD,
            ) * ARM_SPREAD_AMPLITUDE
          ) * armSpreadRampRef.current;

          // Rotate the LEFT upper arm about local Z (+Z spreads it outward).
          ARM_OFFSET_EULER.set(0, 0, armSpread);
          ARM_OFFSET_QUAT.setFromEuler(ARM_OFFSET_EULER);
          leftArm.quaternion.copy(armLeftBaseQuatRef.current).multiply(ARM_OFFSET_QUAT);

          // Mirror the whole left arm chain onto the right arm.
          const humanoid = vrm.humanoid;
          const chest = humanoid.getNormalizedBoneNode('chest');
          const leftShoulder = humanoid.getNormalizedBoneNode('leftShoulder');
          const rightShoulder = humanoid.getNormalizedBoneNode('rightShoulder');
          const rightArm = humanoid.getNormalizedBoneNode('rightUpperArm');
          const leftLowerArm = humanoid.getNormalizedBoneNode('leftLowerArm');
          const rightLowerArm = humanoid.getNormalizedBoneNode('rightLowerArm');
          const leftHand = humanoid.getNormalizedBoneNode('leftHand');
          const rightHand = humanoid.getNormalizedBoneNode('rightHand');
          if (chest && leftShoulder && rightShoulder && rightArm && leftLowerArm && rightLowerArm && leftHand && rightHand) {
            const chestWorld = chest.getWorldQuaternion(new THREE.Quaternion());
            const leftShoulderWorld = new THREE.Quaternion().multiplyQuaternions(chestWorld, leftShoulder.quaternion);
            const leftUpperWorld = new THREE.Quaternion().multiplyQuaternions(leftShoulderWorld, leftArm.quaternion);
            const leftLowerWorld = new THREE.Quaternion().multiplyQuaternions(leftUpperWorld, leftLowerArm.quaternion);
            const leftHandWorld = new THREE.Quaternion().multiplyQuaternions(leftLowerWorld, leftHand.quaternion);

            mirrorArmBoneInto(chestWorld, chestWorld, leftShoulder, rightShoulder);
            const rightShoulderWorld = new THREE.Quaternion().multiplyQuaternions(chestWorld, rightShoulder.quaternion);
            mirrorArmBoneInto(leftShoulderWorld, rightShoulderWorld, leftArm, rightArm);
            const rightUpperWorld = new THREE.Quaternion().multiplyQuaternions(rightShoulderWorld, rightArm.quaternion);
            mirrorArmBoneInto(leftLowerWorld, rightUpperWorld, leftLowerArm, rightLowerArm);
            const rightLowerWorld = new THREE.Quaternion().multiplyQuaternions(rightUpperWorld, rightLowerArm.quaternion);
            mirrorArmBoneInto(leftHandWorld, rightLowerWorld, leftHand, rightHand);

            // Keep the body horizontally centered: the idle clip leans the torso
            // ±1cm laterally, and against a fixed camera that drift reads as one
            // hand spreading wider than the other even though the pose is an exact
            // mirror. Track the shoulder midpoint so the hands stay screen-symmetric.
            // The midpoint is measured RELATIVE to the model position so a dragged
            // model keeps its offset; otherwise the camera re-centers the character
            // and every drag visually snaps back to the middle (pet mode).
            if (!isDraggingRef.current && cameraRef.current && cameraLookAtRef.current && baseCameraPosRef.current) {
              const midX = (
                leftShoulder.getWorldPosition(new THREE.Vector3()).x +
                rightShoulder.getWorldPosition(new THREE.Vector3()).x
              ) / 2;
              const dX = (midX - vrm.scene.position.x) - cameraRef.current.position.x;
              cameraRef.current.position.x += dX;
              baseCameraPosRef.current.x += dX;
              cameraLookAtRef.current.x = cameraRef.current.position.x;
              cameraRef.current.lookAt(cameraLookAtRef.current);
            }
          }
        }
      } else {
        // Idle isn't fully driving the pose (crossfade / one-shot) — clear the
        // captured base so it's re-captured fresh the next time idle takes over.
        armLeftBaseQuatRef.current = null;
        armSpreadRampRef.current = 0;
      }

      // --- Procedural idle animation (fallback when no .vrma) ---
      // Only used when idle animation failed to load
      if (!mixerRef.current && proceduralAnimRef.current) {
        proceduralAnimRef.current.update(delta);
      }

      // --- Subtle head-follow cursor tracking ---
      // The model's VRM lookAt is type 'bone' with near-zero range maps, so it only
      // moves the eyes imperceptibly. Instead, rotate the (normalized) head bone
      // directly toward the cursor, clamped to a small range so the head turns
      // gently. Applied BEFORE vrm.update() so humanoid.update() copies it to the
      // raw head bone. (The .vrma mixer runs above and sets the base head pose;
      // we premultiply a small offset on top.)
      const cursorSmooth = cursorSmoothedRef.current;
      const lerp = 1 - Math.exp(-3.0 * delta);
      cursorSmooth.x += (cursorPosRef.current.x - cursorSmooth.x) * lerp;
      cursorSmooth.y += (cursorPosRef.current.y - cursorSmooth.y) * lerp;

      // Skip head-follow while a one-shot animation (greeting, etc.) is playing —
      // the mixer drives the head pose then, and our offset would fight it.
      if (!currentActionRef.current && headBoneRef.current && headBaseQuatRef.current) {
        const head = headBoneRef.current;
        const MAX_YAW = 0.28; // ~16° horizontal
        const MAX_PITCH = 0.18; // ~10° vertical
        HEAD_OFFSET_EULER.set(
          -cursorSmooth.y * MAX_PITCH,
          cursorSmooth.x * MAX_YAW,
          0,
          'YXZ',
        );
        HEAD_OFFSET_QUAT.setFromEuler(HEAD_OFFSET_EULER);
        // Absolute composition: base (idle pose) × cursor offset.
        // Never read the current quaternion back, otherwise the offset compounds
        // frame-over-frame and the head spins endlessly.
        head.quaternion.copy(headBaseQuatRef.current).multiply(HEAD_OFFSET_QUAT);
      }

      // --- VRM update (spring bones, lookAt, expression blending) ---
      // NOTE: Do NOT call updateMatrixWorld(true) here — it bakes current scale into
      // world matrices, causing the spring bone solver to interpret scale changes as
      // bone movement and push hair upward. Let renderer.render() handle world matrices
      // at the end of each frame (same approach as amica).
      vrm.update(delta);

      // Preserve body orientation: lookAt system may rotate body bones (hips/spine/chest)
      // when the model is off-center, causing the body to "twist." Reset Y rotations so
      // the body always maintains its initial facing direction regardless of model position.
      if (vrm.humanoid) {
        const hipsNode = vrm.humanoid.getNormalizedBoneNode('hips');
        if (hipsNode) hipsNode.rotation.y = 0;
        const spineNode = vrm.humanoid.getNormalizedBoneNode('spine');
        if (spineNode) spineNode.rotation.y = 0;
        const chestNode = vrm.humanoid.getNormalizedBoneNode('chest');
        if (chestNode) chestNode.rotation.y = 0;
      }

      // --- Subtle eye-follow cursor tracking ---
      // Eyes follow the cursor gently too, with smaller angles than the head and a
      // slower smoothing rate so they lag naturally behind it. Applied AFTER
      // vrm.update() on the RAW eye bones so the built-in VRM lookAt applier
      // (which overwrites them during vrm.update) doesn't cancel our rotation.
      // Skipped during one-shot animations (greeting) like the head-follow above.
      //
      // NOTE: we COMPOSE the cursor offset ON TOP of the current raw eye pose
      // rather than pinning a fixed base quaternion. The baked eyeballs are aimed
      // by the VRM lookAt system every frame (it writes the raw eye bones toward
      // the camera target inside vrm.update), and a fixed identity base would
      // point the pupils away from the viewer ("full white" eyes). Since lookAt
      // rewrites the raw eye bones at the top of each frame, multiplying the small
      // cursor offset here never compounds frame-over-frame.
      if (!currentActionRef.current && (leftEyeBoneRef.current || rightEyeBoneRef.current)) {
        const EYE_MAX_YAW = 0.10; // ~6° horizontal
        const EYE_MAX_PITCH = 0.07; // ~4° vertical
        EYE_OFFSET_EULER.set(
          -cursorSmooth.y * EYE_MAX_PITCH,
          cursorSmooth.x * EYE_MAX_YAW,
          0,
          'YXZ',
        );
        EYE_OFFSET_QUAT.setFromEuler(EYE_OFFSET_EULER);
        if (leftEyeBoneRef.current) {
          leftEyeBoneRef.current.quaternion.multiply(EYE_OFFSET_QUAT);
        }
        if (rightEyeBoneRef.current) {
          rightEyeBoneRef.current.quaternion.multiply(EYE_OFFSET_QUAT);
        }
      }

      // Log spring bone state every 60 frames (~1s at 60fps)
      if (!(animate as any)._sbLogCount) (animate as any)._sbLogCount = 0;
      (animate as any)._sbLogCount++;
      if ((animate as any)._sbLogCount % 30 === 1) {
        const sbMgr = (vrm as any).springBoneManager;
        if (sbMgr) {
          const jointsSet = sbMgr.joints;
          const jointsCount = jointsSet ? (jointsSet.size ?? (Array.isArray(jointsSet) ? jointsSet.length : 0)) : 0;
          if (jointsCount > 0) {
            const arr = Array.from(jointsSet);
            // Track hair joints specifically
            const hairJoints = arr.filter((j: any) => {
              const name = (j.bone || j._bone)?.name?.toLowerCase() || '';
              return name.includes('hair') || name.includes('front') || name.includes('side') || name.includes('back');
            });
            if (hairJoints.length > 0) {
              const hairPos = hairJoints.slice(0, 3).map((j: any) => {
                const bone = j.bone || j._bone;
                const wp = bone?.getWorldPosition(new THREE.Vector3());
                return `${bone?.name}=${wp ? `(${wp.x.toFixed(2)},${wp.y.toFixed(2)},${wp.z.toFixed(2)})` : 'N/A'}`;
              }).join(' | ');
              console.log(`[useVRM] frame ${(animate as any)._sbLogCount}: HAIR: ${hairPos} delta=${delta.toFixed(4)}`);
            } else {
              // No hair joints found - log first joint position as reference
              const j0 = arr[0];
              const bone0 = j0.bone || j0._bone;
              const wp = bone0?.getWorldPosition(new THREE.Vector3());
              console.log(`[useVRM] frame ${(animate as any)._sbLogCount}: no hair joints, ref=${bone0?.name} ${wp ? `(${wp.x.toFixed(2)},${wp.y.toFixed(2)},${wp.z.toFixed(2)})` : 'N/A'} delta=${delta.toFixed(4)}`);
            }
          }
        }
      }
    }

    rendererRef.current.render(sceneRef.current, cameraRef.current);

    animationIdRef.current = requestAnimationFrame(animate);
  }, []);

  /**
   * Set expression (emotion) on the VRM model
   */
  const setExpression = useCallback((expressionName: string, weight: number = 1.0) => {
    const vrm = vrmRef.current;
    if (!vrm || !vrm.expressionManager) return;

    const emotionMap = getEmotionMap();
    const blendShapeName = emotionMap[expressionName] || expressionName;

    // Check if this blend shape exists
    if (!(blendShapeName in (vrm.expressionManager.expressionMap || {}))) {
      console.warn(`VRM expression "${blendShapeName}" not found`);
      return;
    }

    // Reset all expression targets to 0, then set the target
    const allExpressions = Object.keys(vrm.expressionManager.expressionMap || {});
    for (const name of allExpressions) {
      expressionTargetsRef.current[name] = 0;
    }
    expressionTargetsRef.current[blendShapeName] = Math.max(0, Math.min(1, weight));

    // Disable auto-blink during emotion, wait for eye to open before applying
    if (autoBlinkRef.current && blendShapeName !== 'neutral') {
      const waitTime = autoBlinkRef.current.setEnable(false);
      if (waitTime > 0) {
        // Eye is currently closed — defer emotion application
        setTimeout(() => {
          expressionTargetsRef.current[blendShapeName] = Math.max(0, Math.min(1, weight));
        }, waitTime * 1000);
      }
    }

    currentEmotionRef.current = blendShapeName;
    setState(prev => ({ ...prev, currentExpression: blendShapeName }));
  }, [getEmotionMap]);

  /**
   * Reset VRM expression to neutral
   */
  const resetExpression = useCallback(() => {
    const vrm = vrmRef.current;
    if (!vrm || !vrm.expressionManager) return;

    const allExpressions = Object.keys(vrm.expressionManager.expressionMap || {});
    for (const name of allExpressions) {
      expressionTargetsRef.current[name] = 0;
    }
    // Set neutral to 1
    if ('neutral' in (vrm.expressionManager.expressionMap || {})) {
      expressionTargetsRef.current['neutral'] = 1.0;
    }

    // Re-enable auto-blink when returning to neutral
    if (autoBlinkRef.current) {
      autoBlinkRef.current.setEnable(true);
    }

    currentEmotionRef.current = 'neutral';
    setState(prev => ({ ...prev, currentExpression: 'neutral' }));
  }, []);

  /**
   * Set viseme (lip-sync) from audio analysis
   * @param visemeName - Viseme name: 'aa', 'ee', 'ih', 'oh', 'ou'
   * @param weight - Intensity 0.0 - 1.0
   */
  const setViseme = useCallback((visemeName: string, weight: number) => {
    const vrm = vrmRef.current;
    if (!vrm || !vrm.expressionManager) return;

    const visemeMap = getVisemeMap();
    const blendShapeName = visemeMap[visemeName];

    if (!blendShapeName || !(blendShapeName in (vrm.expressionManager.expressionMap || {}))) {
      return;
    }

    // Set viseme active weight — animation loop will pick this up
    visemeActiveRef.current[blendShapeName] = Math.max(0, Math.min(1, weight));
  }, [getVisemeMap]);

  /**
   * Clear all active visemes (when speech ends)
   */
  const clearVisemes = useCallback(() => {
    visemeActiveRef.current = {};
    lipSyncRef.current.reset();
    lipSyncAudioRef.current = null;
  }, []);

  /**
   * Start audio-driven lip-sync.
   * Stores the audio element; animation loop reads currentTime each frame
   * to drive visemes from the pre-computed volumes array.
   */
  const startLipSync = useCallback((audio: HTMLAudioElement, volumes: number[], sliceLengthMs: number = 20) => {
    lipSyncRef.current.start(volumes, sliceLengthMs);
    lipSyncAudioRef.current = audio;
  }, []);

  /**
   * Stop lip-sync and clear audio reference
   */
  const stopLipSync = useCallback(() => {
    lipSyncRef.current.reset();
    lipSyncAudioRef.current = null;
  }, []);

  /**
   * Play a VRMA animation by name (e.g. "dance", "greeting").
   * Crossfades from idle, plays once, then crossfades back to idle.
   * Can be triggered externally via CustomEvent 'vrm-play-vrma'.
   */
  const playVRMA = useCallback(async (animationName: string) => {
    const mixer = mixerRef.current;
    const idleAction = idleActionRef.current;
    const vrm = vrmRef.current;
    if (!mixer || !idleAction || !vrm || !animationName) return;

    // Don't stack animations
    if (currentActionRef.current) return;

    try {
      const anim = await loadVRMAnimation(`/animations/${animationName}.vrma`);
      if (!anim) return;

      const clip = anim.createAnimationClip(vrm);
      const action = mixer.clipAction(clip);
      action.clampWhenFinished = true;
      action.loop = THREE.LoopOnce;

      // Crossfade: idle → animation
      idleAction.fadeOut(0.5);
      action.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(0.3).play();
      currentActionRef.current = action;

      // When animation finishes, crossfade back to idle
      const onFinished = () => {
        mixer.removeEventListener('finished', onFinished);
        action.fadeOut(0.5);
        idleAction.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(0.3).play();
        currentActionRef.current = null;
        console.log(`[useVRM] animation '${animationName}' finished, restored idle`);
      };
      mixer.addEventListener('finished', onFinished);
      console.log(`[useVRM] playing animation '${animationName}'`);
    } catch (err) {
      console.warn(`[useVRM] failed to play animation '${animationName}':`, err);
    }
  }, []);

  const playGreeting = useCallback(() => playVRMA('greeting'), [playVRMA]);

  // --- Random pose scheduler ---
  // While the app is idle, occasionally play one of the pose animations so the
  // character isn't statically standing. Skips if another animation is running.
  const RANDOM_POSE_ANIMATIONS = ['peaceSign', 'shoot', 'spin', 'squat', 'dance', 'showFullBody', 'modelPose'];
  const RANDOM_POSE_MIN_MS = 30000;
  const RANDOM_POSE_MAX_MS = 60000;
  const randomPoseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const randomPoseEnabledRef = useRef(false);

  const scheduleRandomPose = useCallback(() => {
    if (randomPoseTimerRef.current) clearTimeout(randomPoseTimerRef.current);
    if (!randomPoseEnabledRef.current) return;
    const delay = RANDOM_POSE_MIN_MS + Math.random() * (RANDOM_POSE_MAX_MS - RANDOM_POSE_MIN_MS);
    randomPoseTimerRef.current = setTimeout(() => {
      randomPoseTimerRef.current = null;
      if (currentActionRef.current) {
        scheduleRandomPose();
        return;
      }
      const name = RANDOM_POSE_ANIMATIONS[Math.floor(Math.random() * RANDOM_POSE_ANIMATIONS.length)];
      playVRMA(name).then(scheduleRandomPose);
    }, delay);
  }, [playVRMA]);

  const setRandomPoseEnabled = useCallback((enabled: boolean) => {
    randomPoseEnabledRef.current = enabled;
    if (enabled) {
      scheduleRandomPose();
    } else if (randomPoseTimerRef.current) {
      clearTimeout(randomPoseTimerRef.current);
      randomPoseTimerRef.current = null;
    }
  }, [scheduleRandomPose]);

  /**
   * Play the greeting ONCE at startup. The character appears in the squat start
   * pose, the greeting plays from that squat (jongkok → berdiri + wave), then
   * crossfades to the standing idle loop which becomes the home state.
   */
  const playStartupGreeting = useCallback(async () => {
    const mixer = mixerRef.current;
    const idleAction = idleActionRef.current;
    const squatHold = squatHoldActionRef.current;
    const vrm = vrmRef.current;
    if (!mixer || !idleAction || !vrm || !squatHold) return;
    if (currentActionRef.current) return;

    try {
      const anim = await loadVRMAnimation('/animations/greeting.vrma');
      if (!anim) return;

      const clip = anim.createAnimationClip(vrm);
      const action = mixer.clipAction(clip);
      action.clampWhenFinished = true;
      action.loop = THREE.LoopOnce;

      // Crossfade: surprise start pose → greeting (starting at the same t≈2.5s
      // frame we held, so the pose is continuous and the wave follows on).
      squatHold.fadeOut(0.3);
      action.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(0.3).play();
      action.time = STARTUP_SURPRISE_HOLD_TIME;
      currentActionRef.current = action;

      // When greeting finishes, crossfade to the STANDING idle (home state)
      const onFinished = () => {
        mixer.removeEventListener('finished', onFinished);
        action.fadeOut(0.5);
        idleAction.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(0.3).play();
        squatHold.stop();
        squatHoldActionRef.current = null;
        currentActionRef.current = null;
        console.log('[useVRM] startup greeting finished — standing idle active');
        // Re-capture head/eye base quats after the standing idle fade-in settles,
        // so cursor-follow offsets are applied relative to the STANDING pose.
        setTimeout(() => {
          // NOTE: the idle clip has NO head track — the head's orientation comes
          // entirely from the neck, and levelHeadToWorldUp() levels it so the head
          // rests straight. The correct cursor-follow base is therefore IDENTITY,
          // NOT the current head bone quaternion: reading the bone here would copy
          // back the stale surprise-pose base that head-follow has been writing all
          // along, pinning the head ndangak/tilted even at center cursor.
          if (headBoneRef.current) {
            headBaseQuatRef.current = new THREE.Quaternion();
          }
          // No fixed eye base needed — eye-follow composes its cursor offset on
          // top of the lookAt-applied raw eye pose each frame.
          // Re-center camera on the standing head height (it was aimed at the
          // squat-height head during the startup greeting).
          if (vrmRef.current?.humanoid && cameraRef.current) {
            const headNode = vrmRef.current.humanoid.getNormalizedBoneNode('head');
            if (headNode) {
              const headPos = headNode.getWorldPosition(new THREE.Vector3());
              cameraRef.current.position.set(headPos.x, headPos.y, 3.0);
              cameraRef.current.lookAt(headPos.x, headPos.y, headPos.z);
              baseCameraPosRef.current = cameraRef.current.position.clone();
              cameraLookAtRef.current = new THREE.Vector3(headPos.x, headPos.y, headPos.z);
              const curScale = currentScaleRef.current || 1.0;
              applyCameraZoom(cameraRef.current, baseCameraPosRef.current, cameraLookAtRef.current, curScale);
            }
          }
          console.log('[useVRM] head/eye base quats re-captured for standing pose');
        }, 400);
      };
      mixer.addEventListener('finished', onFinished);
      console.log('[useVRM] playing startup greeting (from squat)');
    } catch (err) {
      console.warn('[useVRM] failed to play startup greeting:', err);
    }
  }, []);

  /**
   * Wheel handler for scroll-to-resize
   */
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    if (!modelInfo?.scrollToResize) return;

    const direction = e.deltaY > 0 ? -1 : 1;
    const increment = 0.03 * direction;
    const currentActualScale = currentScaleRef.current;
    const newTargetScale = Math.max(
      0.1,
      Math.min(5.0, currentActualScale + increment),
    );
    targetScaleRef.current = newTargetScale;
  }, [modelInfo?.scrollToResize]);

  /**
   * Pointer handlers for dragging the model
   */
  const pointerHandlers = useMemo(() => {
    const onPointerDown = (e: React.PointerEvent) => {
      const vrm = vrmRef.current;
      if (!vrm || !cameraRef.current || !canvasRef.current) return;
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStartScreenRef.current = { x: e.clientX, y: e.clientY };
      dragStartModelRef.current = {
        x: vrm.scene.position.x,
        y: vrm.scene.position.y,
        z: vrm.scene.position.z,
      };
      canvasRef.current.setPointerCapture(e.pointerId);
    };

    const onPointerMove = (e: React.PointerEvent) => {
      if (!isDraggingRef.current || !vrmRef.current || !cameraRef.current || !canvasRef.current) return;
      const canvas = canvasRef.current;
      const cam = cameraRef.current;
      const vrm = vrmRef.current;

      const dx = e.clientX - dragStartScreenRef.current.x;
      const dy = e.clientY - dragStartScreenRef.current.y;

      const vFov = (cam.fov * Math.PI) / 180;
      const dist = cam.position.length();
      const visibleHeightAtOrigin = 2 * Math.tan(vFov / 2) * dist;
      const visibleWidthAtOrigin = visibleHeightAtOrigin * cam.aspect;

      const worldDx = (dx / canvas.clientWidth) * visibleWidthAtOrigin;
      const worldDy = -(dy / canvas.clientHeight) * visibleHeightAtOrigin;

      let newX = dragStartModelRef.current.x + worldDx;
      let newY = dragStartModelRef.current.y + worldDy;

      const MAX_DRAG_X = 4.0;
      const MAX_DRAG_Y = 2.5;
      newX = Math.max(-MAX_DRAG_X, Math.min(MAX_DRAG_X, newX));
      newY = Math.max(-MAX_DRAG_Y, Math.min(MAX_DRAG_Y, newY));

      vrm.scene.position.x = newX;
      vrm.scene.position.y = newY;
    };

    const onPointerUp = (e: React.PointerEvent) => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      if (canvasRef.current) {
        try { canvasRef.current.releasePointerCapture(e.pointerId); } catch { /* ok */ }
      }
    };

    return { onPointerDown, onPointerMove, onPointerUp };
  }, []);

  /**
   * Set cursor position for subtle head-follow tracking.
   * @param viewX normalized -1..1 (right positive)
   * @param viewY normalized -1..1 (up positive)
   */
  const setCursorPosition = useCallback((viewX: number, viewY: number) => {
    cursorPosRef.current = { x: viewX, y: viewY };
  }, []);

  /**
   * Resize handler
   */
  const resize = useCallback(() => {
    if (!rendererRef.current || !cameraRef.current || !canvasRef.current) return;
    const parent = canvasRef.current.parentElement;
    if (!parent) return;

    const width = parent.clientWidth;
    const height = parent.clientHeight;

    if (width === 0 || height === 0) return;

    rendererRef.current.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    rendererRef.current.setSize(width, height);
    cameraRef.current.aspect = width / height;
    cameraRef.current.updateProjectionMatrix();
  }, [canvasRef]);

  // Attach wheel event for scroll-to-resize
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [canvasRef, handleWheel]);

  // Load VRM when model URL changes
  useEffect(() => {
    const url = modelInfo?.url;
    console.log('[useVRM] useEffect triggered, modelInfo?.url:', url, 'prevUrl:', prevModelUrlRef.current);
    if (!url || url === prevModelUrlRef.current) {
      console.log('[useVRM] skipping load -', !url ? 'no url' : 'same as previous');
      return;
    }

    prevModelUrlRef.current = url;
    console.log('[useVRM] model URL changed to:', url);

    // Initialize if not yet
    if (!rendererRef.current) {
      console.log('[useVRM] renderer not initialized, calling initScene');
      initScene();
    } else {
      console.log('[useVRM] renderer already initialized');
    }

    // Small delay to let renderer initialize
    const timer = setTimeout(() => {
      console.log('[useVRM] timeout finished, calling loadVRM');
      loadVRM(url);
    }, 100);

    return () => {
      console.log('[useVRM] cleanup: clearing timeout');
      clearTimeout(timer);
    };
  }, [modelInfo?.url, initScene, loadVRM]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationIdRef.current) {
        cancelAnimationFrame(animationIdRef.current);
      }
      if (vrmRef.current) {
        try { VRMUtils.deepDispose(vrmRef.current.scene); } catch { /* ok */ }
        vrmRef.current = null;
      }
      autoBlinkRef.current = null;
      proceduralAnimRef.current = null;
      if (mixerRef.current) {
        mixerRef.current.stopAllAction();
        mixerRef.current = null;
      }
      idleActionRef.current = null;
      currentActionRef.current = null;
      if (randomPoseTimerRef.current) {
        clearTimeout(randomPoseTimerRef.current);
        randomPoseTimerRef.current = null;
      }
      if (rendererRef.current) {
        rendererRef.current.dispose();
        rendererRef.current = null;
      }
      sceneRef.current = null;
      cameraRef.current = null;
    };
  }, []);

  return {
    isLoaded: state.isLoaded,
    currentExpression: state.currentExpression,
    setExpression,
    resetExpression,
    setViseme,
    clearVisemes,
    startLipSync,
    stopLipSync,
    playVRMA,
    playGreeting,
    setRandomPoseEnabled,
    resize,
    pointerHandlers,
    setCursorPosition,
    isDragging,
  };
}
