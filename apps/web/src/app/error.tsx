"use client";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <main className="route-error">
      <p className="route-error__brand">NINGGUANG</p>
      <strong>Research workspace unavailable</strong>
      <p>The terminal could not complete its initialization sequence.</p>
      <button type="button" onClick={reset}>
        Retry
      </button>
    </main>
  );
}
