import type { Metadata, Viewport } from 'next';
import './globals.css';
import './marketing-corporate.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'https://builiconstruction.com'),
  title: { default: 'BUILI — Construction verification, grounded in evidence', template: '%s — BUILI' },
  description: 'Connect field conditions, drawings, BIM, RFIs, and evidence in one spatial construction verification workflow.',
  applicationName: 'BUILI',
  icons: { icon: '/favicon.png', apple: '/favicon.png' },
  manifest: '/manifest.webmanifest',
  openGraph: {
    type: 'website',
    title: 'BUILI — Know what changed. Prove what happened.',
    description: 'Evidence-grounded construction verification from field capture to review-ready action.',
    images: ['/og-image.svg']
  }
};

export const viewport: Viewport = { themeColor: '#ffffff', colorScheme: 'light', width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}
