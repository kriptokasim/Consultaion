import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Button } from './button'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
  }
  className?: string
}

export function EmptyStateModern({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'animate-fade-in flex flex-col items-center justify-center rounded-2xl border border-border bg-gradient-to-b from-card to-background/50 py-12 px-6 text-center',
        className,
      )}
    >
      {icon && (
        <div className="mb-4 inline-flex rounded-full bg-muted/50 p-4">
          <div className="text-5xl text-muted-foreground/50">{icon}</div>
        </div>
      )}

      <h3 className="heading-serif text-2xl font-semibold text-foreground">
        {title}
      </h3>

      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {description}
      </p>

      {action && (
        <Button
          onClick={action.onClick}
          className="mt-6"
          variant="amber"
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}
