import type { Metadata, Viewport } from 'next';
import './globals.css';
import './marketing-corporate.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_PRODUCT_URL || 'https://builiconstruction.com'),
  title: { default: 'BUILI', template: '%s — BUILI' },
  description: 'Connect field conditions, drawings, BIM, RFIs, and evidence in one spatial construction verification workflow.',
  applicationName: 'BUILI',
  icons: { icon: '/favicon.png', apple: '/favicon.png' },
  manifest: '/manifest.webmanifest',
  openGraph: {
    type: 'website',
    title: 'BUILI — Know what changed. Prove what happened.',
    description: 'Evidence-grounded construction verification from field capture to review-ready action.',
    images: [{ url: '/brand/hero-renovation-v2.webp', width: 1536, height: 1024, alt: 'BUILI construction verification in the field' }]
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
