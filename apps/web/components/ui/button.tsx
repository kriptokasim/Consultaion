import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-all duration-200 disabled:pointer-events-none disabled:opacity-60 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-500 focus-visible:ring-offset-background hover:-translate-y-[1px] hover:shadow-lg active:translate-y-0 active:shadow-sm",
  {
    variants: {
      variant: {
        default:
          'bg-gradient-to-r from-amber-500 via-amber-400 to-amber-300 text-amber-900 shadow-[0_14px_30px_rgba(255,190,92,0.3)] hover:brightness-[1.02] active:brightness-95',
        amber:
          'rounded-full bg-amber-500 text-amber-950 shadow-[0_14px_30px_rgba(245,158,11,0.45)] transition-all duration-200 hover:bg-amber-600 hover:-translate-y-[1px] hover:shadow-[0_18px_40px_rgba(245,158,11,0.55)] active:translate-y-0',
        premium:
          'rounded-full bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 text-white shadow-[0_14px_30px_rgba(59,130,246,0.3)] hover:brightness-[1.03] hover:shadow-[0_18px_36px_rgba(59,130,246,0.4)] active:brightness-95',
        destructive:
          'bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60',
        outline:
          'border border-amber-300/80 bg-white text-amber-900 shadow-[0_8px_24px_rgba(112,73,28,0.12)] hover:bg-amber-50/70 hover:text-amber-900 dark:border-amber-800 dark:bg-stone-900 dark:text-amber-50 dark:hover:bg-amber-900/30',
        secondary:
          'border border-amber-200/60 bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 dark:border-amber-900/40 dark:bg-stone-900/60 dark:text-amber-50',
        ghost:
          'text-amber-800 hover:bg-amber-100/70 hover:text-amber-900 dark:text-amber-100 dark:hover:bg-amber-900/30',
        muted:
          'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        link: 'text-amber-800 underline-offset-4 hover:underline dark:text-amber-200',
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
