export function dataStatusLabel(isStale: boolean, isMock: boolean): string {
  if (isMock) return "MOCK DATA";
  return isStale ? "STALE" : "EOD CURRENT";
}
