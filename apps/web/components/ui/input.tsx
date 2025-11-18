"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type = "text", ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-stone-200 bg-white px-3 py-2 text-sm text-stone-800 ring-offset-background placeholder:text-stone-500 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:shadow-lg focus-visible:shadow-amber-200/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-amber-900/50 dark:bg-stone-900 dark:text-amber-50 dark:placeholder:text-amber-200/70",
          className,
        )}
        ref={ref}
        {...props}
      />
    )
  },
)
Input.displayName = "Input"

export { Input }
