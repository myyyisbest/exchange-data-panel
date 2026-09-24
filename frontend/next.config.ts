import type { NextConfig } from "next";

const flaskOrigin =
  process.env.FLASK_API_ORIGIN?.replace(/\/$/, "") ||
  "http://127.0.0.1:41010";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${flaskOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
