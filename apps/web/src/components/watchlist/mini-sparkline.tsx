import type { Numberish } from "@/lib/api/types";

type Props = {
  values: Numberish[];
  direction: "up" | "down" | "flat";
};

export function MiniSparkline({ values, direction }: Props) {
  const points = values.map(Number).filter(Number.isFinite);
  if (points.length < 2) return <span className="sparkline-empty" aria-label="No sparkline data" />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const path = points
    .map((value, index) => {
      const x = (index / (points.length - 1)) * 74;
      const y = 22 - ((value - min) / range) * 18;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className={`sparkline sparkline--${direction}`} viewBox="0 0 74 26" role="img" aria-label={`${direction} 30-session price sparkline`} preserveAspectRatio="none">
      <polyline points={path} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
