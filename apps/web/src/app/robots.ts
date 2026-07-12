import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: '*', allow: '/', disallow: ['/app/', '/login', '/signup'] }], sitemap: 'https://builiconstruction.com/sitemap.xml' };
}
