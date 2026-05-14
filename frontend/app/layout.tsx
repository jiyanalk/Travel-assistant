import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Travel Assistant MVP",
  description: "Frontend scaffold for the travel planning agent.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
