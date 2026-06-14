'use client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function SettingsError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="container mx-auto max-w-4xl p-6">
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Settings unavailable</AlertTitle>
        <AlertDescription>
          <p className="mt-2 text-sm">{error.message || "Could not load settings."}</p>
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
