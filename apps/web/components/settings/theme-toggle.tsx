'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { Sun, Moon, Monitor } from 'lucide-react'

const themes = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
] as const

export function ThemeToggle() {
    const { theme, setTheme } = useTheme()
    const [mounted, setMounted] = useState(false)

    useEffect(() => setMounted(true), [])

    if (!mounted) {
        return (
            <div className="card-elevated max-w-2xl space-y-4 p-6">
                <div className="h-5 w-32 animate-pulse rounded bg-muted" />
                <div className="h-10 w-64 animate-pulse rounded-xl bg-muted" />
            </div>
        )
    }

    return (
        <div className="card-elevated max-w-2xl space-y-4 p-6">
            <div>
                <p className="heading-serif text-lg font-semibold text-foreground">
                    Appearance
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                    Choose how Consultaion looks. Select a theme or sync with your system preference.
                </p>
            </div>

            <div className="inline-flex rounded-xl border border-border bg-secondary p-1">
                {themes.map(({ value, label, icon: Icon }) => {
                    const active = theme === value
                    return (
                        <button
                            key={value}
                            onClick={() => setTheme(value)}
                            className={`
                flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-background
                ${active
                                    ? 'bg-background text-primary shadow-sm'
                                    : 'text-muted-foreground hover:text-foreground'
                                }
              `}
                            aria-pressed={active}
                        >
                            <Icon className="h-4 w-4" />
                            {label}
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
