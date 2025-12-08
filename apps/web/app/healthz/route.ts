import { NextResponse } from 'next/server'

export async function GET() {
  const env = process.env.NEXT_PUBLIC_APP_ENV || 'local'
  
  return NextResponse.json({
    status: 'ok',
    env,
    timestamp: new Date().toISOString(),
  })
}
