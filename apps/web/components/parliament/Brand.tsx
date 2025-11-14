import Image from "next/image";
import { cn } from "@/lib/utils";

type BrandProps = {
  variant?: "mark" | "logotype";
  tone?: "stone" | "amber";
  className?: string;
  height?: number;
};

export default function Brand({ variant = "mark", tone = "stone", className, height = 32 }: BrandProps) {
  const src =
    variant === "logotype"
      ? "/brand/rc-logotype.svg"
      : tone === "amber"
        ? "/brand/rc-mark-amber.svg"
        : "/brand/rc-mark.svg";
  return (
    <Image
      src={src}
      alt={variant === "logotype" ? "Rosetta Chamber" : "Rosetta Chamber mark"}
      priority={variant === "mark"}
      width={height}
      height={height}
      className={cn("select-none", className)}
    />
  );
}
