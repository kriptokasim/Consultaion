'use client'

import { useEffect, useRef, useState } from 'react'

interface AnimatedCounterProps {
  value: number
  duration?: number
  prefix?: string
  suffix?: string
  decimals?: number
}

export function AnimatedCounter({
  value,
  duration = 1000,
  prefix = '',
  suffix = '',
  decimals = 0,
}: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState(0)
  const animationRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startTimeRef = useRef<number | null>(null)

  useEffect(() => {
    const startAnimation = () => {
      startTimeRef.current = Date.now()

      const animate = () => {
        if (!startTimeRef.current) return

        const elapsed = Date.now() - startTimeRef.current
        const progress = Math.min(elapsed / duration, 1)

        const easeOut = 1 - Math.pow(1 - progress, 3)
        const currentValue = Math.floor(value * easeOut * Math.pow(10, decimals)) / Math.pow(10, decimals)

        setDisplayValue(currentValue)

        if (progress < 1) {
          animationRef.current = setTimeout(animate, 16)
        }
      }

      animate()
    }

    startAnimation()

    return () => {
      if (animationRef.current) clearTimeout(animationRef.current)
    }
  }, [value, duration, decimals])

  const formatted = displayValue.toFixed(decimals)

  return (
    <span className="tabular-nums">
      {prefix}
      {formatted}
      {suffix}
    </span>
  )
}
