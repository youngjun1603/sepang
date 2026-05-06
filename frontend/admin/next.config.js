const path = require("path");

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
module.exports = nextConfig;
