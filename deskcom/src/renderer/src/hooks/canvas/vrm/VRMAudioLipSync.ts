// @ts-nocheck
/**
 * VRM Audio Lip-Sync
 *
 * Drives viseme blend shapes from a pre-computed volumes array (RMS per chunk).
 * Each chunk represents `sliceLengthMs` milliseconds of audio.
 * The current playback position is mapped to the correct chunk index,
 * producing smooth per-frame lip-sync synced to audio.
 */
export class VRMAudioLipSync {
  private volumes: number[] = [];
  private sliceLengthMs: number = 20;
  private smoothVolume: number = 0;
  private prevChunkIndex: number = -1;
  private smoothing: number = 0.4;

  /**
   * Initialize with a new audio chunk's volumes.
   * @param volumes - RMS values per chunk (0.0-1.0, normalized)
   * @param sliceLengthMs - Duration of each chunk in milliseconds (default 20)
   */
  start(volumes: number[], sliceLengthMs: number = 20) {
    this.volumes = volumes;
    this.sliceLengthMs = Math.max(1, sliceLengthMs);
    this.smoothVolume = 0;
    this.prevChunkIndex = -1;
  }

  /**
   * Get the current lip-sync volume for a given audio playback time.
   * Uses chunk-aligned lookup with interpolation for smoothness.
   *
   * @param currentTimeSeconds - Current audio element playback position in seconds
   * @returns Smoothed volume 0.0-1.0
   */
  update(currentTimeSeconds: number): number {
    if (this.volumes.length === 0) return 0;

    const currentTimeMs = currentTimeSeconds * 1000;
    const chunkIndex = Math.floor(currentTimeMs / this.sliceLengthMs);

    if (chunkIndex < 0 || chunkIndex >= this.volumes.length) {
      this.smoothVolume *= 0.8;
      return this.smoothVolume;
    }

    const targetVolume = this.volumes[chunkIndex];

    // Extra boost: make lip-sync more responsive
    const boosted = Math.min(1.0, targetVolume * 1.5);

    // Smooth toward target — fast attack, slow release for natural motion
    if (boosted > this.smoothVolume) {
      // Attack: fast ramp up
      this.smoothVolume += (boosted - this.smoothVolume) * 0.6;
    } else {
      // Release: slower decay
      this.smoothVolume += (boosted - this.smoothVolume) * 0.3;
    }

    this.prevChunkIndex = chunkIndex;
    return this.smoothVolume;
  }

  /**
   * Reset lip-sync state (call when audio ends or is interrupted)
   */
  reset() {
    this.volumes = [];
    this.smoothVolume = 0;
    this.prevChunkIndex = -1;
  }
}
