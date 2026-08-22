"use client";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <main className="route-error">
      <p className="route-error__brand">KEJORA</p>
      <strong>Research workspace unavailable</strong>
      <p>The research workspace could not finish loading.</p>
      <button type="button" onClick={reset}>
        Retry
      </button>
    </main>
  );
}
