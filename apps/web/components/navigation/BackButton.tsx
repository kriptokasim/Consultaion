"use client";

import { useRouter } from "next/navigation";
import { Link } from "next-view-transitions";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

interface BackButtonProps {
  className?: string;
  label?: string;
  onClick?: () => void;
  href?: string;
}

export default function BackButton({ className, label = "Back", onClick, href }: BackButtonProps) {
  const router = useRouter();

  const handleBack = (e: React.MouseEvent) => {
    if (href) return; // Let Link handle it
    e.preventDefault();
    if (onClick) {
      onClick();
    } else {
      router.back();
    }
  };

  const buttonClasses = cn(
    "group inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/80 px-4 py-1.5 text-xs font-semibold text-slate-700 shadow-sm backdrop-blur transition-all duration-200 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 active:scale-[0.98] dark:border-slate-700/80 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:hover:text-white",
    className
  );

  const innerContent = (
    <>
      <ArrowLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
      <span>{label}</span>
    </>
  );

  if (href) {
    return (
      <Link href={href} className={buttonClasses}>
        {innerContent}
      </Link>
    );
  }

  return (
    <button onClick={handleBack} className={buttonClasses}>
      {innerContent}
    </button>
  );
}
