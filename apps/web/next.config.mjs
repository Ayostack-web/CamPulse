/** @type {import('next').NextConfig} */
import withPWA from 'next-pwa';

const nextConfig = {
  experimental: {
    typedRoutes: true
  },
  async rewrites() {
    const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:4000').trim();
    return [
      {
        source: '/api/auth/:path*',
        destination: '/api/auth/:path*',
      },
      {
        source: '/api/v1/:path*',
        destination: `${apiBaseUrl}/api/v1/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${apiBaseUrl}/api/v1/:path*`,
      },
    ];
  },
};

const pwaConfig = withPWA({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      // Never cache API responses in the service worker:
      // material file endpoints return short-lived signed URLs, and the PDF
      // bytes themselves are cached in IndexedDB by lib/pdf-cache.ts.
      urlPattern: /\/api\//,
      handler: 'NetworkOnly',
      method: 'GET',
      options: {
        cacheName: 'api-cache',
      },
    },
  ],
});

export default pwaConfig(nextConfig);
