const path = require("path");
const withPWA = require("@ducanh2912/next-pwa").default({
  dest: "public",
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === "development",
  fallbacks: {
    document: "/offline.html",
  },
  runtimeCaching: [
    {
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
  output: process.env.CAPACITOR === "true" ? "export" : undefined,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  transpilePackages: ["@sepang/shared"],
  webpack: (config) => {
    config.resolve.modules.push(path.resolve(__dirname, "node_modules"));
    return config;
  },
};

module.exports = withPWA(nextConfig);
