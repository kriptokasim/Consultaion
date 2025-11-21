import { cn } from "@/lib/utils"

interface SkeletonLoaderProps {
  className?: string
  count?: number
  variant?: "text" | "circle" | "rect"
}

export function SkeletonLoader({
  className,
  count = 1,
  variant = "rect",
}: SkeletonLoaderProps) {
  const items = Array.from({ length: count })

  return (
    <>
      {items.map((_, idx) => (
        <div
          key={idx}
          className={cn(
            "animate-pulse rounded-lg bg-muted/50",
            variant === "circle" && "rounded-full",
            variant === "text" && "h-4 w-3/4",
            variant === "rect" && "h-12 w-full",
            className,
          )}
        />
      ))}
    </>
  )
}

export function CardSkeleton() {
  return (
    <div className="space-y-4 rounded-lg border border-border p-6">
      <SkeletonLoader variant="text" className="h-6 w-1/3" />
      <div className="space-y-3">
        <SkeletonLoader variant="text" className="h-4 w-full" />
        <SkeletonLoader variant="text" className="h-4 w-5/6" />
      </div>
      <SkeletonLoader variant="rect" className="h-8 w-24" />
    </div>
  )
}

export function TableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, idx) => (
        <div key={idx} className="flex items-center gap-4 rounded-lg border border-border p-4">
          <SkeletonLoader variant="circle" className="h-10 w-10 flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <SkeletonLoader variant="text" className="h-4 w-1/3" />
            <SkeletonLoader variant="text" className="h-3 w-1/4" />
          </div>
          <SkeletonLoader variant="text" className="h-4 w-20" />
        </div>
      ))}
    </div>
  )
}
