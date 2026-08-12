/* eslint-disable no-param-reassign */
import { memo, useRef, useEffect, useCallback, useState } from 'react';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { useForceIgnoreMouse } from '@/hooks/utils/use-force-ignore-mouse';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { getPlatform } from '@/platforms';

const DEFAULT_EMOT = '-_-';
const TALKING_MOUTHS = ['_', 'o', 'O', '□'];
const BLINK_INTERVAL = 3000;
const BLINK_DURATION = 150;

interface OrbConfig {
  x: number;
  y: number;
  scale: number;
}

function defaultConfig(): OrbConfig {
  return {
    x: 0.5,
    y: 0.55,
    scale: 1,
  };
}

export const OrbCanvas = memo(
  (): JSX.Element => {
    const { forceIgnoreMouse } = useForceIgnoreMouse();
    const { modelInfo } = useLive2DConfig();
    const { aiState } = useAiState();
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [orbConfig, setOrbConfig] = useLocalStorage<OrbConfig>('orbConfig', defaultConfig());

    // Live animation state (refs to avoid re-renders)
    const animRef = useRef({
      volumes: [] as number[],
      sliceLength: 20,
      audio: null as HTMLAudioElement | null,
      emot: DEFAULT_EMOT,
      emotSetAt: 0,
      talking: false,
      lastVolume: 0,
      time: 0,
      dragging: false,
      isDragging: false,
      dragStartX: 0,
      dragStartY: 0,
      dragStartConfig: { x: 0.5, y: 0.55 },
    });

    const scaleRef = useRef(orbConfig.scale);
    const scrollToResize = modelInfo?.scrollToResize !== false;

    // Update scaleRef when config changes from persistence
    useEffect(() => {
      scaleRef.current = orbConfig.scale;
    }, [orbConfig.scale]);

    // ---- Audio task / lip-sync events (same events useAudioTask dispatches) ----
    useEffect(() => {
      const onAudioTask = (e: CustomEvent) => {
        const { expressions } = e.detail || {};
        if (expressions && expressions.length > 0) {
          const emot = String(expressions[0]);
          animRef.current.emot = emot;
          animRef.current.emotSetAt = performance.now();
        }
      };

      const onLipSyncStart = (e: CustomEvent) => {
        const { audio, volumes, sliceLength } = e.detail || {};
        animRef.current.audio = audio || null;
        animRef.current.volumes = volumes || [];
        animRef.current.sliceLength = sliceLength || 20;
        animRef.current.talking = true;
      };

      const onLipSyncStop = () => {
        animRef.current.talking = false;
        animRef.current.volumes = [];
        animRef.current.audio = null;
        animRef.current.lastVolume = 0;
      };

      window.addEventListener('vrm-audio-task', onAudioTask as EventListener);
      window.addEventListener('vrm-lip-sync-start', onLipSyncStart as EventListener);
      window.addEventListener('vrm-lip-sync-stop', onLipSyncStop as EventListener);

      return () => {
        window.removeEventListener('vrm-audio-task', onAudioTask as EventListener);
        window.removeEventListener('vrm-lip-sync-start', onLipSyncStart as EventListener);
        window.removeEventListener('vrm-lip-sync-stop', onLipSyncStop as EventListener);
      };
    }, []);

    // Reset emot to default when idle lingers
    useEffect(() => {
      if (aiState === AiStateEnum.IDLE) {
        const timer = setTimeout(() => {
          if (!animRef.current.talking) {
            animRef.current.emot = DEFAULT_EMOT;
          }
        }, 6000);
        return () => clearTimeout(timer);
      }
      return undefined;
    }, [aiState]);

    // ---- Rendering loop ----
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return undefined;
      const ctx = canvas.getContext('2d');
      if (!ctx) return undefined;

      let rafId = 0;
      let blinkTimer = performance.now() + BLINK_INTERVAL;
      let blinkActive = false;
      let blinkStart = 0;

      const resizeCanvas = () => {
        const dpr = window.devicePixelRatio || 1;
        canvas.width = window.innerWidth * dpr;
        canvas.height = window.innerHeight * dpr;
        canvas.style.width = `${window.innerWidth}px`;
        canvas.style.height = `${window.innerHeight}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      };
      resizeCanvas();
      window.addEventListener('resize', resizeCanvas);

      const draw = (now: number) => {
        rafId = requestAnimationFrame(draw);
        const anim = animRef.current;
        anim.time = now / 1000;

        const w = window.innerWidth;
        const h = window.innerHeight;

        // Center position from config (fraction of viewport) + drag offset
        const config = orbConfig;
        const cx = config.x * w;
        const cy = config.y * h;

        ctx.clearRect(0, 0, w, h);

        // ----- Current volume (synced to audio.currentTime) -----
        let volume = 0;
        if (anim.audio && anim.volumes.length > 0) {
          const t = anim.audio.currentTime * 1000;
          const idx = Math.min(
            anim.volumes.length - 1,
            Math.floor(t / anim.sliceLength),
          );
          volume = anim.volumes[idx] || 0;
        } else if (anim.talking) {
          // Fallback idle shimmer while talking frame is queued
          volume = anim.lastVolume;
        }
        // Smooth attack/release
        anim.lastVolume += (volume - anim.lastVolume) * (anim.talking ? 0.6 : 0.15);

        // ----- Blink state -----
        if (now > blinkTimer) {
          blinkActive = true;
          blinkStart = now;
          blinkTimer = now + BLINK_INTERVAL;
        }
        if (blinkActive && now - blinkStart > BLINK_DURATION) {
          blinkActive = false;
        }

        // ----- Emot rendering (3-char eye/mouth/eye) -----
        const base = anim.emot || DEFAULT_EMOT;
        let [lEye, mouth, rEye] = [base[0] ?? '-', base[1] ?? '_', base[2] ?? '-'];
        if (blinkActive && !anim.talking) {
          lEye = 'x';
          rEye = 'x';
        }
        if (anim.talking) {
          const amp = Math.min(1, anim.lastVolume * 2.2);
          mouth = TALKING_MOUTHS[Math.min(
            TALKING_MOUTHS.length - 1,
            Math.floor(amp * TALKING_MOUTHS.length),
          )];
        }
        const emot = `[${lEye}${mouth}${rEye}]`;

        // ----- Orb radius -----
        const baseR = Math.min(w, h) * 0.09 * scaleRef.current;

        // ----- Soundwave ring (undulating circle) -----
        const ringPoints = 96;
        const waveAmp = baseR * 0.14;
        const idleAmp = baseR * 0.03;
        const k = 5; // lobes
        const phase = anim.time * 2;
        const volBoost = anim.lastVolume * baseR * 0.45;

        ctx.beginPath();
        for (let i = 0; i <= ringPoints; i += 1) {
          const theta = (i / ringPoints) * Math.PI * 2;
          const wave =
            waveAmp * Math.sin(k * theta + phase) * anim.lastVolume +
            idleAmp * Math.sin(3 * theta + anim.time * 1.2) +
            volBoost * (0.5 + 0.5 * Math.sin(2 * theta - phase));
          const r = baseR * 1.55 + wave;
          const px = cx + Math.cos(theta) * r;
          const py = cy + Math.sin(theta) * r;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.strokeStyle = 'rgba(80, 180, 255, 0.7)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Second ring for depth
        ctx.beginPath();
        for (let i = 0; i <= ringPoints; i += 1) {
          const theta = (i / ringPoints) * Math.PI * 2;
          const wave =
            waveAmp * 0.6 * Math.sin(k * theta + phase + Math.PI / 4) * anim.lastVolume +
            idleAmp * Math.sin(3 * theta + anim.time * 1.2 + 1);
          const r = baseR * 1.75 + wave;
          const px = cx + Math.cos(theta) * r;
          const py = cy + Math.sin(theta) * r;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.strokeStyle = 'rgba(80, 180, 255, 0.25)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // ----- Outer halo -----
        const glow = ctx.createRadialGradient(cx, cy, baseR * 0.5, cx, cy, baseR * 2.6);
        glow.addColorStop(0, 'rgba(60, 150, 255, 0.25)');
        glow.addColorStop(1, 'rgba(60, 150, 255, 0)');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(cx, cy, baseR * 2.6, 0, Math.PI * 2);
        ctx.fill();

        // ----- Orb body (blue radial gradient) -----
        const pulse = 1 + anim.lastVolume * 0.06 + Math.sin(anim.time * 1.5) * 0.015;
        const r = baseR * pulse;
        const orbGrad = ctx.createRadialGradient(
          cx - r * 0.35, cy - r * 0.35, r * 0.1,
          cx, cy, r,
        );
        orbGrad.addColorStop(0, '#cfeaff');
        orbGrad.addColorStop(0.35, '#5ab6ff');
        orbGrad.addColorStop(0.75, '#1e7fe0');
        orbGrad.addColorStop(1, '#0b4a9e');
        ctx.fillStyle = orbGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();

        // ----- Emot text -----
        ctx.fillStyle = 'rgba(10, 30, 60, 0.85)';
        ctx.font = `bold ${Math.round(r * 0.42)}px 'Courier New', monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(emot, cx, cy);

        // Small status dot while talking
        if (anim.talking) {
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.beginPath();
          ctx.arc(cx + r * 0.55, cy - r * 0.55, 3, 0, Math.PI * 2);
          ctx.fill();
        }
      };
      rafId = requestAnimationFrame(draw);

      return () => {
        cancelAnimationFrame(rafId);
        window.removeEventListener('resize', resizeCanvas);
      };
      // orbConfig captured per frame is fine via ref-like closure for center;
      // dragging writes via setOrbConfig (React state) — see pointer handlers.
    }, [orbConfig]);

    // ---- Pointer: drag to move, wheel to resize ----
    const handlePointerDown = useCallback((e: React.PointerEvent) => {
      const anim = animRef.current;
      anim.dragging = true;
      anim.isDragging = false;
      anim.dragStartX = e.clientX;
      anim.dragStartY = e.clientY;
      anim.dragStartConfig = { x: orbConfig.x, y: orbConfig.y };
    }, [orbConfig]);

    const handlePointerMove = useCallback((e: React.PointerEvent) => {
      const anim = animRef.current;
      if (!anim.dragging) return;
      const dx = e.clientX - anim.dragStartX;
      const dy = e.clientY - anim.dragStartY;
      if (!anim.isDragging && Math.hypot(dx, dy) > 4) {
        anim.isDragging = true;
      }
      if (anim.isDragging) {
        const w = window.innerWidth;
        const h = window.innerHeight;
        setOrbConfig({
          ...orbConfig,
          x: Math.min(1, Math.max(0, anim.dragStartConfig.x + dx / w)),
          y: Math.min(1, Math.max(0, anim.dragStartConfig.y + dy / h)),
        });
      }
    }, [orbConfig, setOrbConfig]);

    const handlePointerUp = useCallback(() => {
      animRef.current.dragging = false;
    }, []);

    const handleWheel = useCallback((e: React.WheelEvent) => {
      if (!scrollToResize) return;
      e.preventDefault();
      const dir = e.deltaY > 0 ? -0.05 : 0.05;
      scaleRef.current = Math.min(2.5, Math.max(0.3, scaleRef.current + dir));
      setOrbConfig({ ...orbConfig, scale: scaleRef.current });
    }, [scrollToResize, orbConfig, setOrbConfig]);

    // Hover passthrough
    useEffect(() => {
      const container = containerRef.current;
      if (!container) return undefined;

      const onEnter = () => getPlatform().updateComponentHover('orb-model', true);
      const onLeave = () => getPlatform().updateComponentHover('orb-model', false);
      container.addEventListener('mouseenter', onEnter);
      container.addEventListener('mouseleave', onLeave);
      return () => {
        container.removeEventListener('mouseenter', onEnter);
        container.removeEventListener('mouseleave', onLeave);
      };
    }, []);

    const handleContextMenu = useCallback((e: React.MouseEvent) => {
      e.preventDefault();
      getPlatform().showContextMenu();
    }, []);

    return (
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          overflow: 'hidden',
          position: 'relative',
          pointerEvents: forceIgnoreMouse ? 'none' : 'auto',
          cursor: animRef.current.isDragging ? 'grabbing' : 'default',
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onWheel={handleWheel}
        onContextMenu={handleContextMenu}
      >
        <canvas
          ref={canvasRef}
          style={{
            width: '100%',
            height: '100%',
            display: 'block',
          }}
        />
      </div>
    );
  },
);

OrbCanvas.displayName = 'OrbCanvas';

export default OrbCanvas;
