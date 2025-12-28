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
        <linearGradient id="rosetta-parliament" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#EFF6FF" />
          <stop offset="100%" stopColor="#DBEAFE" />
        </linearGradient>
        <linearGradient id="rosetta-parliament-dark" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#1E3A5F" />
          <stop offset="100%" stopColor="#1E40AF" />
        </linearGradient>
      </defs>
      {/* Outer circle with parliament blue */}
      <circle cx="40" cy="40" r="36" fill="url(#rosetta-parliament)" stroke="#1E3A5F" strokeWidth="2" className="dark:fill-[url(#rosetta-parliament-dark)] dark:stroke-blue-400" />
      <circle cx="40" cy="40" r="26" fill="none" stroke="#3B82F6" strokeWidth="2" strokeDasharray="4 3" />
      <circle cx="40" cy="40" r="18" fill="#F0F9FF" stroke="#1E40AF" strokeWidth="1.5" className="dark:fill-slate-800 dark:stroke-blue-400" />

      {/* Seats / benches - now blue */}
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
            fill="#3B82F6"
            stroke="#1E40AF"
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
        fill="#DBEAFE"
        stroke="#1E3A5F"
        strokeWidth="1"
        className="dark:fill-slate-700 dark:stroke-blue-400"
      />
      <path d="M34 38h12M34 42h8" stroke="#1E40AF" strokeWidth="1.2" strokeLinecap="round" className="dark:stroke-blue-400" />
    </svg>
  );
};

export default RosettaChamberLogo;
