import type { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    { url: 'https://builiconstruction.com', lastModified, changeFrequency: 'weekly', priority: 1 },
    { url: 'https://builiconstruction.com/privacy', lastModified, changeFrequency: 'monthly', priority: .4 },
    { url: 'https://builiconstruction.com/terms', lastModified, changeFrequency: 'monthly', priority: .4 },
  ];
}
