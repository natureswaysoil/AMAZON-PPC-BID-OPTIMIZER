import './globals.css'
import { DM_Mono, Syne } from 'next/font/google'

const dmMono = DM_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-dm-mono',
})

const syne = Syne({
  subsets: ['latin'],
  weight: ['600', '700', '800'],
  variable: '--font-syne',
})

export const metadata = {
  title: "Nature's Way Soil / Amazon Ad Manager",
  description: 'AOV-aware dynamic bid optimization',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${dmMono.variable} ${syne.variable}`}>
      <body className="bg-nws-bg text-nws-text font-mono min-h-screen">{children}</body>
    </html>
  )
}
