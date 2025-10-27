import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { cn } from '@/lib/utils'
import { Toaster } from 'sonner'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'PHANTOM Security AI',
  description: 'Autonomous vulnerability detection powered by artificial intelligence',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={cn('min-h-screen bg-background antialiased', inter.className)}>
        {children}
        <Toaster theme="dark" position="top-right" />
      </body>
    </html>
  )
}