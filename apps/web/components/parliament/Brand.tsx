import Image from "next/image";
import { cn } from "@/lib/utils";

type BrandProps = {
  variant?: "mark" | "logotype";
  tone?: "stone" | "amber";
  className?: string;
  height?: number;
};

export default function Brand({ variant = "mark", className, height = 32 }: BrandProps) {
  const src = "/brand/consultaion-logo.png";
  return (
    <div
      className={cn("flex items-center justify-center shrink-0", className)}
      style={{ height: `${height}px` }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Consultaion"
        className="h-full w-auto object-contain"
        draggable={false}
      />
    </div>
  );
}
