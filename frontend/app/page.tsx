'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto flex min-h-screen items-center justify-center p-6">
        <div className="text-center">
          <h1 className="mb-4 text-6xl font-bold text-white">
            PHANTOM
            <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              {' '}Security AI
            </span>
          </h1>
          
          <p className="mb-8 text-xl text-gray-300">
            Autonomous vulnerability detection powered by artificial intelligence
          </p>
          
          <div className="space-x-4">
            <Link href="/dashboard">
              <Button size="lg" className="bg-purple-600 hover:bg-purple-700">
                Launch Dashboard
              </Button>
            </Link>
            
            <Button variant="outline" size="lg">
              Learn More
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}