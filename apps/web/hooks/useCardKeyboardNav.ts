/**
 * Keyboard navigation hook for model card tabs.
 *
 * FH110: ArrowRight/Left/Home/End navigation between model cards.
 */

"use client";

import { useCallback, useEffect, useRef } from "react";

export function useCardKeyboardNav(cardCount: number) {
  const containerRef = useRef<HTMLDivElement>(null);
  const focusIndexRef = useRef<number>(-1);

  const focusCard = useCallback((index: number) => {
    if (!containerRef.current) return;
    const cards = containerRef.current.querySelectorAll<HTMLElement>("[data-model-card]");
    if (cards[index]) {
      cards[index].focus();
      focusIndexRef.current = index;
    }
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle when a model card is focused
      const target = e.target as HTMLElement;
      if (!target?.dataset?.modelCard && target.closest?.("[data-model-card]") === null) return;

      const cards = container.querySelectorAll<HTMLElement>("[data-model-card]");
      const currentIdx = Array.from(cards).indexOf(
        target.dataset?.modelCard ? target : target.closest("[data-model-card]") as HTMLElement
      );
      if (currentIdx === -1) return;

      switch (e.key) {
        case "ArrowRight":
          e.preventDefault();
          focusCard(Math.min(currentIdx + 1, cards.length - 1));
          break;
        case "ArrowLeft":
          e.preventDefault();
          focusCard(Math.max(currentIdx - 1, 0));
          break;
        case "Home":
          e.preventDefault();
          focusCard(0);
          break;
        case "End":
          e.preventDefault();
          focusCard(cards.length - 1);
          break;
      }
    };

    container.addEventListener("keydown", handleKeyDown);
    return () => container.removeEventListener("keydown", handleKeyDown);
  }, [cardCount, focusCard]);

  return { containerRef };
}
