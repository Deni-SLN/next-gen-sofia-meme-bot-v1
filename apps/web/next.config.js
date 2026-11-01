/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
      {
        source: '/Signals',
        destination: '/signals',
      },
      {
        source: '/Portfolio',
        destination: '/portfolio',
      },
      {
        source: '/Risk',
        destination: '/risk',
      },
    ];
  },
};

// Updated configuration for SOFIA Trenches
module.exports = nextConfig;

