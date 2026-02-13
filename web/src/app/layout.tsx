import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Polymarket Agent Console',
  description: 'Live status dashboard for BTC 15m decision agent',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
