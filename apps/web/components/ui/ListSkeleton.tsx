export interface ListSkeletonProps {
  rows?: number;
  className?: string;
}

/**
 * Canonical New UX loading state: hairline/list rhythm with aria-busy
 * (SCREEN-SPEC "State family"). No spinners/gradients.
 */
export function ListSkeleton({ rows = 3, className = "" }: ListSkeletonProps) {
  return (
    <div
      className={`new-ux-list-skeleton ${className}`.trim()}
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="new-ux-list-skeleton__row" />
      ))}
    </div>
  );
}
