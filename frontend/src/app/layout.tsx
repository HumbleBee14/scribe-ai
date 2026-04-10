import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/lib/theme";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vulcan OmniPro 220 Assistant",
  description: "Multimodal support agent for the Vulcan OmniPro 220 welding system.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* Preload Mermaid CDN so iframes render instantly (cached by browser) */}
        <link
          rel="preload"
          href="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"
          as="script"
          crossOrigin="anonymous"
        />
      </head>
      <body className="min-h-full flex flex-col bg-[--background] text-[--foreground]">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
