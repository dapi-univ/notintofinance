import { DashboardClient } from "@/components/dashboard/dashboard-client";

const tickerPattern = /^[A-Z0-9]{1,12}$/;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ ticker?: string }>;
}) {
  const params = await searchParams;
  const requestedTicker = params.ticker?.toUpperCase();
  const initialTicker = requestedTicker && tickerPattern.test(requestedTicker) ? requestedTicker : "BBCA";
  return <DashboardClient initialTicker={initialTicker} />;
}
