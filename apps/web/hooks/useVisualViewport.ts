'use client'

import { useEffect, useState } from 'react'

export interface VisualViewportState {
  viewportHeight: number
  viewportWidth: number
  offsetTop: number
  isKeyboardOpen: boolean
  orientation: 'portrait' | 'landscape'
}

export function useVisualViewport(): VisualViewportState {
  const [state, setState] = useState<VisualViewportState>({
    viewportHeight: typeof window !== 'undefined' ? window.innerHeight : 800,
    viewportWidth: typeof window !== 'undefined' ? window.innerWidth : 600,
    offsetTop: 0,
    isKeyboardOpen: false,
    orientation: 'portrait',
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.visualViewport) return

    const handleResizeOrScroll = () => {
      const vv = window.visualViewport
      if (!vv) return

      const heightDiff = window.innerHeight - vv.height
      // If visual viewport is significantly shorter than window height, keyboard is open
      const isKeyboardOpen = heightDiff > 120

      setState({
        viewportHeight: vv.height,
        viewportWidth: vv.width,
        offsetTop: vv.offsetTop,
        isKeyboardOpen,
        orientation: vv.width > vv.height ? 'landscape' : 'portrait',
      })
    }

    const vv = window.visualViewport
    vv.addEventListener('resize', handleResizeOrScroll)
    vv.addEventListener('scroll', handleResizeOrScroll)
    window.addEventListener('resize', handleResizeOrScroll)

    // Initial check
    handleResizeOrScroll()

    return () => {
      vv.removeEventListener('resize', handleResizeOrScroll)
      vv.removeEventListener('scroll', handleResizeOrScroll)
      window.removeEventListener('resize', handleResizeOrScroll)
    }
  }, [])

  return state
}
