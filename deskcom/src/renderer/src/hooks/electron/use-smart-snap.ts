export interface WindowRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SnapConfig {
  threshold?: number;
  screenMargin?: number;
}

export function calculateSnapPosition(
  currentPos: { x: number; y: number },
  elementSize: { width: number; height: number },
  otherRects: WindowRect[],
  config: SnapConfig = {},
): { x: number; y: number; snappedX: boolean; snappedY: boolean } {
  const threshold = config.threshold ?? 16;
  const screenMargin = config.screenMargin ?? 12;

  let targetX = currentPos.x;
  let targetY = currentPos.y;
  let snappedX = false;
  let snappedY = false;

  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  // 1. Screen Edge Snapping
  // Left edge
  if (Math.abs(targetX - screenMargin) < threshold) {
    targetX = screenMargin;
    snappedX = true;
  }
  // Right edge
  else if (Math.abs(targetX + elementSize.width - (viewportWidth - screenMargin)) < threshold) {
    targetX = viewportWidth - screenMargin - elementSize.width;
    snappedX = true;
  }

  // Top edge
  if (Math.abs(targetY - screenMargin) < threshold) {
    targetY = screenMargin;
    snappedY = true;
  }
  // Bottom edge
  else if (Math.abs(targetY + elementSize.height - (viewportHeight - screenMargin)) < threshold) {
    targetY = viewportHeight - screenMargin - elementSize.height;
    snappedY = true;
  }

  // 2. Sibling Window Snapping (if not snapped to screen edge)
  for (const rect of otherRects) {
    const myLeft = targetX;
    const myRight = targetX + elementSize.width;
    const myTop = targetY;
    const myBottom = targetY + elementSize.height;

    const otherLeft = rect.x;
    const otherRight = rect.x + rect.width;
    const otherTop = rect.y;
    const otherBottom = rect.y + rect.height;

    // Check vertical alignment for horizontal snapping
    const isVerticallyOverlapping = myBottom > otherTop && myTop < otherBottom;
    if (isVerticallyOverlapping) {
      // Snap my left edge to other right edge
      if (!snappedX && Math.abs(myLeft - (otherRight + screenMargin)) < threshold) {
        targetX = otherRight + screenMargin;
        snappedX = true;
      }
      // Snap my right edge to other left edge
      else if (!snappedX && Math.abs(myRight - (otherLeft - screenMargin)) < threshold) {
        targetX = otherLeft - screenMargin - elementSize.width;
        snappedX = true;
      }
    }

    // Check horizontal alignment for vertical snapping
    const isHorizontallyOverlapping = myRight > otherLeft && myLeft < otherRight;
    if (isHorizontallyOverlapping) {
      // Snap my top edge to other bottom edge
      if (!snappedY && Math.abs(myTop - (otherBottom + screenMargin)) < threshold) {
        targetY = otherBottom + screenMargin;
        snappedY = true;
      }
      // Snap my bottom edge to other top edge
      else if (!snappedY && Math.abs(myBottom - (otherTop - screenMargin)) < threshold) {
        targetY = otherTop - screenMargin - elementSize.height;
        snappedY = true;
      }
    }
  }

  return { x: targetX, y: targetY, snappedX, snappedY };
}
