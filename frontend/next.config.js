/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  // Avoid Windows ENOENT/rename failures on .next/cache during hot reload.
  webpack: (config, { dev }) => {
    if (dev && process.platform === "win32") {
      config.cache = { type: "memory" };
    }
    return config;
  },
};

module.exports = nextConfig;
