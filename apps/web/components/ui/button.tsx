import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-all duration-200 disabled:pointer-events-none disabled:opacity-60 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-focus focus-visible:ring-offset-background hover:-translate-y-[1px] hover:shadow-lg active:translate-y-0 active:shadow-sm",
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground shadow-smooth hover:brightness-[1.02] active:brightness-95',
        amber:
          'rounded-full bg-amber-500 text-amber-950 shadow-[0_14px_30px_rgba(245,158,11,0.45)] transition-all duration-200 hover:bg-amber-600 hover:-translate-y-[1px] hover:shadow-[0_18px_40px_rgba(245,158,11,0.55)] active:translate-y-0',
        premium:
          'rounded-full bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 text-white shadow-[0_14px_30px_rgba(59,130,246,0.3)] hover:brightness-[1.03] hover:shadow-[0_18px_36px_rgba(59,130,246,0.4)] active:brightness-95',
        destructive:
          'bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60',
        outline:
          'border border-border bg-background text-foreground shadow-sm hover:bg-secondary hover:text-foreground dark:bg-background dark:text-foreground dark:hover:bg-secondary',
        secondary:
          'border border-border bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80',
        ghost:
          'text-foreground hover:bg-secondary hover:text-foreground',
        muted:
          'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        link: 'text-accent-secondary underline-offset-4 hover:underline',
        success:
          'bg-success text-success-foreground shadow-smooth hover:bg-success/90 hover:shadow-smooth-lg',
        'soft-amber':
          'border border-amber-200 bg-amber-50 text-amber-900 shadow-smooth hover:bg-amber-100 hover:shadow-smooth-lg dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-100 dark:hover:bg-amber-950/40',
      },
      size: {
        default: 'h-9 px-4 py-2 has-[>svg]:px-3',
        sm: 'h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5',
        lg: 'h-10 rounded-md px-6 has-[>svg]:px-4',
        icon: 'size-9',
        'icon-sm': 'size-8',
        'icon-lg': 'size-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : 'button'

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
