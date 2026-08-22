import { KejoraMark } from "@/components/brand/kejora-mark";

export default function Loading() {
  return (
    <main className="route-loading" aria-label="Loading dashboard">
      <div className="route-loading__rail"><span><KejoraMark /></span></div>
      <div className="route-loading__list">
        <strong>KEJORA</strong>
        <span>Equity Research Tools</span>
      </div>
      <div className="route-loading__chart" />
    </main>
  );
}
