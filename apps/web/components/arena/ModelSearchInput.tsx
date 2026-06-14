'use client'

import React from 'react'
import { Search } from 'lucide-react'

interface ModelSearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function ModelSearchInput({ value, onChange, placeholder = 'Search models or providers...' }: ModelSearchInputProps) {
  return (
    <div className="px-6 py-3 border-b border-border/40 bg-muted/30 flex items-center gap-2">
      <Search className="h-4 w-4 text-muted-foreground shrink-0" />
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ fontSize: '16px' }}
        className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none py-1"
      />
    </div>
  )
}
