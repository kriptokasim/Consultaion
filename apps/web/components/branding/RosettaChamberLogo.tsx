import type { FC } from "react";

type LogoProps = {
  size?: number;
  className?: string;
};

const RosettaChamberLogo: FC<LogoProps> = ({ size = 40, className }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 80 80"
      className={className}
      aria-hidden="true"
      role="img"
    >
      <defs>
        <linearGradient id="rosetta-amber" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef9e7" />
          <stop offset="100%" stopColor="#fdf3d0" />
        </linearGradient>
      </defs>
      <circle cx="40" cy="40" r="36" fill="url(#rosetta-amber)" stroke="#8b5e34" strokeWidth="2" />
      <circle cx="40" cy="40" r="26" fill="none" stroke="#d97706" strokeWidth="2" strokeDasharray="4 3" />
      <circle cx="40" cy="40" r="18" fill="#fff8e6" stroke="#b45309" strokeWidth="1.5" />

      {/* Seats / benches */}
      {Array.from({ length: 6 }).map((_, idx) => {
        const angle = (idx / 6) * Math.PI * 2;
        const x = 40 + Math.cos(angle) * 22;
        const y = 40 + Math.sin(angle) * 22;
        const rotate = (angle * 180) / Math.PI;
        return (
          <rect
            key={idx}
            x={x - 2}
            y={y - 6}
            width="4"
            height="12"
            rx="1.5"
            fill="#fbbf24"
            stroke="#92400e"
            strokeWidth="0.8"
            transform={`rotate(${rotate} ${x} ${y})`}
          />
        );
      })}

      {/* Central tablet */}
      <rect
        x="32"
        y="34"
        width="16"
        height="12"
        rx="3"
        fill="#fef3c7"
        stroke="#78350f"
        strokeWidth="1"
      />
      <path d="M34 38h12M34 42h8" stroke="#b45309" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
};

export default RosettaChamberLogo;
