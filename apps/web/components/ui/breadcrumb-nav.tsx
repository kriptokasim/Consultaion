import Link from 'next/link'
import { ChevronRight, Home } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface BreadcrumbItem {
  label: string
  href?: string
  active?: boolean
}

interface BreadcrumbNavProps {
  items: BreadcrumbItem[]
  className?: string
}

export function BreadcrumbNav({ items, className }: BreadcrumbNavProps) {
  return (
    <nav
      className={cn('flex items-center gap-1 text-sm', className)}
      aria-label="Breadcrumb"
    >
      <Link
        href="/"
        className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-muted-foreground transition-colors hover:text-foreground hover:bg-muted/50"
      >
        <Home className="h-4 w-4" />
        <span className="sr-only">Home</span>
      </Link>

      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-1">
          <ChevronRight className="h-4 w-4 text-muted-foreground/60" />
          {item.href && !item.active ? (
            <Link
              href={item.href}
              className="rounded-md px-2 py-1.5 text-muted-foreground transition-colors hover:text-foreground hover:bg-muted/50"
            >
              {item.label}
            </Link>
          ) : (
            <span
              className={cn(
                'rounded-md px-2 py-1.5',
                item.active ? 'text-foreground font-semibold' : 'text-muted-foreground',
              )}
              aria-current={item.active ? 'page' : undefined}
            >
              {item.label}
            </span>
          )}
        </div>
      ))}
    </nav>
  )
}
