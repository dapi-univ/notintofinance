export const WATCHLIST_ROW_HEIGHT = 62;
export const WATCHLIST_OVERSCAN = 8;
export const WATCHLIST_INITIAL_VIEWPORT_HEIGHT = 620;

type VirtualRange = {
  start: number;
  end: number;
  offsetTop: number;
  totalHeight: number;
};

export function getFixedRowVirtualRange(
  itemCount: number,
  scrollTop: number,
  viewportHeight: number,
  rowHeight = WATCHLIST_ROW_HEIGHT,
  overscan = WATCHLIST_OVERSCAN,
): VirtualRange {
  const totalHeight = Math.max(0, itemCount) * rowHeight;
  if (itemCount <= 0 || rowHeight <= 0 || viewportHeight <= 0) {
    return { start: 0, end: 0, offsetTop: 0, totalHeight };
  }

  const maximumScrollTop = Math.max(0, totalHeight - viewportHeight);
  const safeScrollTop = Math.min(Math.max(0, scrollTop), maximumScrollTop);
  const firstVisible = Math.floor(safeScrollTop / rowHeight);
  const lastVisible = Math.ceil((safeScrollTop + viewportHeight) / rowHeight);
  const start = Math.max(0, firstVisible - overscan);
  const end = Math.min(itemCount, lastVisible + overscan);

  return {
    start,
    end,
    offsetTop: start * rowHeight,
    totalHeight,
  };
}
