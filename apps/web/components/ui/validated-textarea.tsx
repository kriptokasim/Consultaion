"use client";

import { forwardRef, TextareaHTMLAttributes, useMemo } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type ValidatedTextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  value: string;
  minLength?: number;
  maxLength?: number;
};

const ValidatedTextarea = forwardRef<HTMLTextAreaElement, ValidatedTextareaProps>(
  ({ value, minLength = 0, maxLength, className, ...props }, ref) => {
    const status = useMemo(() => {
      if (!value) return "idle";
      if (minLength && value.trim().length < minLength) return "warning";
      if (maxLength && value.length > maxLength) return "error";
      if (maxLength && value.length > maxLength - 200) return "notice";
      return "ok";
    }, [value, minLength, maxLength]);

    const helper =
      status === "warning"
        ? `Add at least ${minLength} characters`
        : status === "notice"
          ? `${maxLength! - value.length} characters left`
          : status === "error"
            ? "Prompt exceeds the length limit"
            : `${value.length}${maxLength ? ` / ${maxLength}` : ""} characters`;

    return (
      <div className="space-y-2">
        <Textarea
          ref={ref}
          value={value}
          className={cn(
            "min-h-32 resize-none border-stone-200 focus-visible:ring-amber-500",
            status === "error" && "border-rose-300 focus-visible:ring-rose-500",
            className,
          )}
          {...props}
        />
        <div
          className={cn(
            "text-xs",
            status === "error" && "text-rose-600",
            status === "warning" && "text-amber-700",
            status === "notice" && "text-amber-600",
            status === "ok" && "text-stone-500",
          )}
        >
          {helper}
        </div>
      </div>
    );
  },
);

ValidatedTextarea.displayName = "ValidatedTextarea";

export default ValidatedTextarea;
