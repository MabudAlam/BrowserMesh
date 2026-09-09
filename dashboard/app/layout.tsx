import type { Metadata } from "next"
import { Geist, Geist_Mono, Familjen_Grotesk } from "next/font/google"
import "./globals.css"
import { cn } from "@/lib/utils"

const fontSans = Geist({ subsets: ["latin"], variable: "--font-sans" })
const fontMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" })
const fontHeading = Familjen_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["400", "500", "600", "700"],
})

export const metadata: Metadata = {
  title: "BrowserMesh",
  description: "Browser-agnostic headed browsers, isolated per Pod",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("dark", "antialiased", fontSans.variable, fontMono.variable, fontHeading.variable)}>
      <body>{children}</body>
    </html>
  )
}
