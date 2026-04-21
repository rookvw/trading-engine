/** @type {import('next').NextConfig} */
const BACKEND = process.env.BACKEND_URL || "http://backend:8000";

const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*/",
        destination: `${BACKEND}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${BACKEND}/api/:path*/`,
      },
    ];
  },
};

module.exports = nextConfig;
