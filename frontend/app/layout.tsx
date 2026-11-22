import type { Metadata } from "next";
import type { ReactNode } from "react";

import { TopBar } from "../components/TopBar";
import { TopBarProvider } from "../components/TopBarSlot";
import "./globals.css";

export const metadata: Metadata = {
  title: "Blog Studio",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopBarProvider>
          <TopBar />
          {children}
        </TopBarProvider>
      </body>
    </html>
  );
}
