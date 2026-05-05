/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: process.env.CAPACITOR === "true" ? "export" : undefined,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
}
module.exports = nextConfig
