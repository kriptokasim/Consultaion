import type { FC } from "react";

type GlyphProps = {
  size?: number;
  className?: string;
};

const RosettaGlyphMini: FC<GlyphProps> = ({ size = 18, className }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
    >
      <circle cx="16" cy="16" r="15" fill="#fef3c7" stroke="#92400e" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="10" fill="none" stroke="#d97706" strokeWidth="1.5" strokeDasharray="3 2" />
      {Array.from({ length: 4 }).map((_, idx) => {
        const angle = (idx / 4) * Math.PI * 2;
        const x = 16 + Math.cos(angle) * 12;
        const y = 16 + Math.sin(angle) * 12;
        return <circle key={idx} cx={x} cy={y} r="2" fill="#fbbf24" stroke="#92400e" strokeWidth="0.7" />;
      })}
      <rect x="12.5" y="12.5" width="7" height="5" rx="1.5" fill="#fff9ed" stroke="#b45309" strokeWidth="0.8" />
    </svg>
  );
};

export default RosettaGlyphMini;
