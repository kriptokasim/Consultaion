import { cn } from '@/lib/utils'

interface FloatingButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode
  label?: string
  variant?: 'primary' | 'secondary'
}

export function FloatingButton({
  icon,
  label,
  variant = 'primary',
  className,
  ...props
}: FloatingButtonProps) {
  return (
    <button
      className={cn(
        'group fixed bottom-6 right-6 z-40 inline-flex items-center justify-center gap-2 rounded-full p-4 font-semibold shadow-smooth-lg transition-all duration-300 hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-500 active:scale-95',
        variant === 'primary' &&
          'bg-amber-500 text-amber-950 hover:bg-amber-600 hover:shadow-smooth-xl',
        variant === 'secondary' &&
          'border border-amber-200 bg-white text-amber-900 hover:bg-amber-50 dark:border-amber-900/40 dark:bg-stone-900 dark:text-amber-50 dark:hover:bg-amber-950/20',
        className,
      )}
      {...props}
    >
      <span className="text-2xl">{icon}</span>
      {label && (
        <span className="absolute -left-24 rounded-lg bg-foreground px-3 py-1.5 text-xs font-medium text-background opacity-0 transition-opacity group-hover:opacity-100 whitespace-nowrap">
          {label}
        </span>
      )}
    </button>
  )
}
