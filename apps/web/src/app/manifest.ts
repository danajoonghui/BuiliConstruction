import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'BUILI', short_name: 'BUILI', description: 'Construction verification intelligence',
    start_url: '/app', display: 'standalone', background_color: '#ffffff', theme_color: '#50C878',
    icons: [{ src: '/favicon.png', sizes: '512x512', type: 'image/png' }]
  };
}
