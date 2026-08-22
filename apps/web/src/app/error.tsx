"use client";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <main className="route-error">
      <p>Dashboard workspace could not be loaded.</p>
      <button type="button" onClick={reset}>
        Retry
      </button>
    </main>
  );
}
