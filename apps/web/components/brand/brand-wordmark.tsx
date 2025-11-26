import { cn } from '@/lib/utils'

interface BrandWordmarkProps {
    /**
     * Size variant for the wordmark
     * @default "md"
     */
    size?: 'sm' | 'md' | 'lg'
    /**
     * Whether to render inline with surrounding text
     * @default false
     */
    inline?: boolean
    /**
     * Additional CSS classes
     */
    className?: string
}

const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
}

/**
 * BrandWordmark - Canonical Consultaion wordmark component
 *
 * Renders "Consultaion" as a single token with visual emphasis on "AI".
 * The wordmark is split into three presentational segments:
 * - "Consult" (brand.primary)
 * - "AI" (brand.accent)
 * - "on" (brand.primary)
 */
export function BrandWordmark({
    size = 'md',
    inline = false,
    className = '',
}: BrandWordmarkProps) {
    return (
        <span
            className={cn(
                'font-sans font-semibold tracking-tight',
                sizeClasses[size],
                inline ? 'inline' : 'block',
                className
            )}
        >
            <span className="text-brand-primary">Consult</span>
            <span className="text-brand-accent">AI</span>
            <span className="text-brand-primary">on</span>
        </span>
    )
}
