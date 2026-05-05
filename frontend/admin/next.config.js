/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Vercel은 output 미설정, CAPACITOR=true 시 정적 내보내기
  output: process.env.CAPACITOR === "true" ? "export" : undefined,
}
module.exports = nextConfig
