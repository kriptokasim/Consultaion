import * as React from 'react'

import { cn } from '@/lib/utils'

function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        'flex min-h-[100px] w-full rounded-lg border border-input bg-background px-4 py-3 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:shadow-smooth focus-visible:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 resize-none dark:border-slate-600 dark:bg-slate-800',
        className,
      )}
      {...props}
    />
  )
}

export { Textarea }
