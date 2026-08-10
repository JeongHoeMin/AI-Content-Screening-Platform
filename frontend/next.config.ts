import type { NextConfig } from "next";

// The FastAPI backend issues its settings session cookie with SameSite=strict,
// so the browser must see the API as same-origin. Proxying through Next rather
// than enabling CORS keeps that cookie working and leaves the backend untouched.
const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Ship a self-contained server so the runtime image does not need node_modules.
  output: "standalone",
  // Next gzips proxied responses by default, and the compressor holds SSE chunks
  // until its buffer fills — the recommendation progress stream then delivers
  // nothing until the run ends. Browsers hit this because they send
  // `Accept-Encoding: gzip`; curl does not, which is why it looked healthy.
  compress: false,
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
