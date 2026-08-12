import type { VRMExpressionManager } from '@pixiv/three-vrm';

const BLINK_CLOSE_MAX = 0.12;
const BLINK_OPEN_MAX = 5.0;

export class AutoBlink {
  private _expressionManager: VRMExpressionManager;
  private _remainingTime: number;
  private _isOpen: boolean;
  private _isAutoBlink: boolean;
  private _holdClosed: boolean;
  private _holdRemaining: number;

  constructor(expressionManager: VRMExpressionManager) {
    this._expressionManager = expressionManager;
    this._remainingTime = 0;
    this._isAutoBlink = true;
    this._isOpen = true;
    this._holdClosed = false;
    this._holdRemaining = 0;
  }

  public setEnable(isAuto: boolean): number {
    this._isAutoBlink = isAuto;

    if (!this._isOpen) {
      return this._remainingTime;
    }

    return 0;
  }

  /**
   * Close the eyes (AI-driven) and optionally auto-release after a duration.
   * A short duration (e.g. 0.35s) gives a slow drowsy blink for `sleepy`
   * instead of holding the eyes shut for the whole utterance. Releasing
   * immediately with holdClosed(false) hands control back to auto-blink.
   */
  public holdClosed(closed: boolean, holdDuration: number = 0) {
    this._holdClosed = closed;
    this._holdRemaining = holdDuration;
    if (closed) {
      this._isOpen = false;
      this._remainingTime = 0;
      this._expressionManager.setValue('blink', 1);
    } else {
      this._isOpen = true;
      // Don't snap the eye open here — the expression smoothing loop eases it
      // back once the blink target is cleared. Wait a full blink-open cycle
      // before auto-blink is allowed to close again, so the eye doesn't slam
      // shut right after being released.
      this._remainingTime = BLINK_OPEN_MAX;
    }
  }

  public update(delta: number) {
    if (this._holdClosed) {
      this._expressionManager.setValue('blink', 1);
      if (this._holdRemaining > 0) {
        this._holdRemaining -= delta;
        if (this._holdRemaining <= 0) {
          // Auto-release: become open so the smoothing loop eases the eye back.
          this._holdClosed = false;
          this._isOpen = true;
          this._remainingTime = BLINK_OPEN_MAX;
          this._expressionManager.setValue('blink', 0);
        }
      }
      return;
    }

    if (this._remainingTime > 0) {
      this._remainingTime -= delta;
      return;
    }

    if (this._isOpen && this._isAutoBlink) {
      this.close();
      return;
    }

    this.open();
  }

  private close() {
    this._isOpen = false;
    this._remainingTime = BLINK_CLOSE_MAX;
    this._expressionManager.setValue('blink', 1);
  }

  private open() {
    this._isOpen = true;
    this._remainingTime = BLINK_OPEN_MAX;
    this._expressionManager.setValue('blink', 0);
  }
}
