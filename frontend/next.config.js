/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  // Reduce Windows hot-reload ENOENT / client-reference-manifest corruption.
  webpack: (config, { dev, isServer }) => {
    if (dev && process.platform === "win32") {
      config.cache = { type: "memory" };
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
        ignored: ["**/.next/**", "**/node_modules/**"],
      };
    }
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
      };
    }
    return config;
  },
  onDemandEntries: {
    maxInactiveAge: 60 * 1000,
    pagesBufferLength: 5,
  },
};

module.exports = nextConfig;
