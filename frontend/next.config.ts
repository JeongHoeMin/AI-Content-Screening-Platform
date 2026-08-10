import type { NextConfig } from "next";

// The FastAPI backend issues its settings session cookie with SameSite=strict,
// so the browser must see the API as same-origin. Proxying through Next rather
// than enabling CORS keeps that cookie working and leaves the backend untouched.
const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Ship a self-contained server so the runtime image does not need node_modules.
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
