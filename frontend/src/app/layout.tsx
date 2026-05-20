import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediSync — Emergency Supply Matching",
  description:
    "Event-driven emergency blood and organ supply-chain matching, built on Azure.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="container">{children}</main>
        <footer className="site-footer">
          MediSync — a portfolio project. Azure Functions · Cosmos DB · Event
          Grid · Durable Functions.
        </footer>
      </body>
    </html>
  );
}
