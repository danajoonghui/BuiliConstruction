import { fileURLToPath } from 'node:url';

const production = process.env.NODE_ENV === 'production';
const configuredApiOrigin = (() => {
  const fallback = production ? 'https://api.builiconstruction.com' : 'http://localhost:8000';
  try { return new URL(process.env.NEXT_PUBLIC_API_URL || fallback).origin; }
  catch { return 'https://api.builiconstruction.com'; }
})();

// Next.js emits inline bootstrap scripts. Until the app adopts per-request CSP
// nonces, `unsafe-inline` is required for those framework scripts to execute.
// `unsafe-eval` is limited to development because Turbopack/HMR requires it.
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${production ? '' : " 'unsafe-eval'"} https://accounts.google.com/gsi/client`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${configuredApiOrigin} https://api.builiconstruction.com https://accounts.google.com${production ? '' : ' ws: wss:'}`,
  "frame-src https://accounts.google.com",
  "media-src 'self' blob:",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'"
].join('; ');

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  output: 'standalone',
  outputFileTracingRoot: fileURLToPath(new URL('.', import.meta.url)),
  experimental: { optimizePackageImports: ['lucide-react'] },
  images: { formats: ['image/avif', 'image/webp'] },
  async headers() {
    return [{
      source: '/(.*)',
      headers: [
        { key: 'Content-Security-Policy', value: contentSecurityPolicy },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Permissions-Policy', value: 'camera=(self), microphone=(self), geolocation=(self)' },
        { key: 'Cross-Origin-Opener-Policy', value: 'same-origin-allow-popups' },
        { key: 'Cross-Origin-Resource-Policy', value: 'same-site' },
        ...(production ? [{ key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' }] : [])
      ]
    }];
  }
};

export default nextConfig;
