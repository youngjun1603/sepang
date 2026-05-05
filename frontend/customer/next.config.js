const withPWA = require("next-pwa")({
  dest: "public",
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === "development",
  fallbacks: {
    document: "/offline.html",
  },
  runtimeCaching: [
    {
      // API 응답은 캐시하지 않음 — 항상 최신 주문 상태 필요
      urlPattern: /^https:\/\/api\.sepang\.kr\/.*/i,
      handler: "NetworkOnly",
    },
    {
      urlPattern: /^https:\/\/fonts\.(gstatic|googleapis)\.com\/.*/i,
      handler: "CacheFirst",
      options: { cacheName: "google-fonts", expiration: { maxEntries: 20, maxAgeSeconds: 365 * 24 * 60 * 60 } },
    },
    {
      urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i,
      handler: "CacheFirst",
      options: { cacheName: "static-images", expiration: { maxEntries: 64, maxAgeSeconds: 30 * 24 * 60 * 60 } },
    },
    {
      urlPattern: /\.(?:js|css)$/i,
      handler: "StaleWhileRevalidate",
      options: { cacheName: "static-assets", expiration: { maxEntries: 64, maxAgeSeconds: 7 * 24 * 60 * 60 } },
    },
  ],
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // CAPACITOR=true 시 정적 내보내기(out/), Vercel은 output 미설정
  output: process.env.CAPACITOR === "true" ? "export" : undefined,
};

module.exports = withPWA(nextConfig);
