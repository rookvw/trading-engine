import type { Metadata } from "next";
import "./globals.css";
import ClientNav from "./components/ClientNav";

export const metadata: Metadata = {
  title: "투자 운영",
  appleWebApp: { capable: true, title: "투자 운영", statusBarStyle: "black-translucent" },
  themeColor: "#08080E",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="bg-void">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover, user-scalable=no" />
      </head>
      <body className="max-w-2xl mx-auto min-h-screen pb-20 bg-base">
        <main className="px-4 pt-4">
          {children}
        </main>
        <ClientNav />
      </body>
    </html>
  );
}
