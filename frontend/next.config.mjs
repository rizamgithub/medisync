/** @type {import('next').NextConfig} */
const nextConfig = {
  // Fully static export — the app is a set of client-rendered pages that call
  // the Function App APIs directly. Deploys to Azure Static Web Apps (Free
  // tier) with no Node server (context.md §3).
  output: "export",

  // next/image optimization needs a server; disable it for the static export.
  images: { unoptimized: true },

  // Emit /route/index.html instead of /route.html — friendlier for static
  // hosts when a deep link is opened directly.
  trailingSlash: true,
};

export default nextConfig;
