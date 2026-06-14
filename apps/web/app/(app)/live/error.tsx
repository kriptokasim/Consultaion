'use client'

import { useEffect } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function LiveError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="p-6 max-w-2xl mx-auto">
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Something went wrong</AlertTitle>
        <AlertDescription>
          <p className="mt-2 text-sm">{error.message || "An unexpected error occurred."}</p>
          {error.digest && (
            <p className="mt-1 text-xs text-muted-foreground">Reference: {error.digest}</p>
          )}
          <Button variant="outline" className="mt-4" onClick={() => reset()}>
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  )
}
