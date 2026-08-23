import type { Metadata } from "next";
import { Manrope } from "next/font/google";

import { QueryProvider } from "@/components/providers/query-provider";

import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

export const metadata: Metadata = {
  title: "KEJORA · Equity Research Tools",
  description: "Premium end-of-day Indonesian equities research workspace.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={manrope.variable}>
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
