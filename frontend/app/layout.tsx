import './globals.css'

export const metadata = {
  title: 'Amazon PPC Optimizer',
  description: 'AOV-aware dynamic bid optimization',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
