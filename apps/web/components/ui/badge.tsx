import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center justify-center rounded-full border px-3 py-1 text-xs font-semibold w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1.5 [&>svg]:pointer-events-none transition-all duration-200 overflow-hidden',
  {
    variants: {
      variant: {
        default:
          'border-primary/20 bg-primary/10 text-primary [a&]:hover:bg-primary/20',
        secondary:
          'border-secondary/20 bg-secondary/10 text-secondary-foreground [a&]:hover:bg-secondary/20',
        destructive:
          'border-destructive/20 bg-destructive/10 text-destructive [a&]:hover:bg-destructive/20',
        outline:
          'border-border text-foreground [a&]:hover:bg-muted/50',
        success:
          'border-success/20 bg-success-light text-success dark:bg-success-dark/20',
        warning:
          'border-warning/20 bg-warning-light text-warning dark:bg-warning-dark/20',
        info:
          'border-info/20 bg-info-light text-info dark:bg-info-dark/20',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<'span'> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'span'

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
