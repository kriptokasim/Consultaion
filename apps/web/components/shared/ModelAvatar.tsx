"use client";

import React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

interface ModelAvatarProps {
  provider?: string;
  modelId?: string;
  displayName?: string;
  logoUrl?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export default function ModelAvatar({
  provider,
  modelId,
  displayName,
  logoUrl,
  size = "md",
  className,
}: ModelAvatarProps) {
  const normProvider = provider?.toLowerCase() || "";
  const name = displayName || modelId || provider || "?";
  const initials = name.slice(0, 2).toUpperCase();

  const sizeClasses = {
    sm: "h-6 w-6 text-[10px]",
    md: "h-9 w-9 text-xs",
    lg: "h-12 w-12 text-sm",
  };

  // Curated premium gradients for fallbacks
  const themeGradients: Record<string, string> = {
    openai: "from-emerald-400 to-teal-600 text-white",
    anthropic: "from-orange-400 to-amber-600 text-white",
    google: "from-blue-400 via-purple-500 to-pink-500 text-white",
    meta: "from-blue-500 to-indigo-600 text-white",
    mistral: "from-deep-orange-500 to-orange-600 text-white",
    cohere: "from-violet-400 to-purple-600 text-white",
  };

  const defaultGradient = "from-slate-400 to-slate-600 text-white";
  const gradientClass = themeGradients[normProvider] || defaultGradient;

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center rounded-xl font-bold tracking-wider shadow-sm transition-all duration-300 hover:scale-105",
        "border border-white/10 dark:border-black/20",
        sizeClasses[size],
        gradientClass,
        className
      )}
      title={name}
    >
      {logoUrl ? (
        <Image
          src={logoUrl}
          alt={name}
          width={48}
          height={48}
          unoptimized
          className="h-full w-full rounded-xl object-cover"
          onError={(e) => {
            // Remove image on error to fallback to initials
            (e.target as HTMLElement).style.display = "none";
          }}
        />
      ) : (
        <span>{initials}</span>
      )}
      <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-background bg-emerald-500" />
    </div>
  );
}
