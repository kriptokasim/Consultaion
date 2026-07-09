'use client'

import { useEffect, useRef } from "react";

type Shortcut = {
  combo: string;
  handler: (event: KeyboardEvent) => void;
  enabled?: boolean;
};

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  const shortcutsRef = useRef(shortcuts);
  
  useEffect(() => {
    shortcutsRef.current = shortcuts;
  }, [shortcuts]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      shortcutsRef.current.forEach((shortcut) => {
        if (shortcut.enabled === false) return;
        if (matchCombo(event, shortcut.combo)) {
          event.preventDefault();
          shortcut.handler(event);
        }
      });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

function matchCombo(event: KeyboardEvent, combo: string) {
  const parts = combo.toLowerCase().split("+").map((part) => part.trim());
  const key = parts.pop();
  if (!key) return false;
  const metaChecks: Record<string, boolean> = {
    ctrl: event.ctrlKey,
    cmd: event.metaKey,
    meta: event.metaKey,
    alt: event.altKey,
    shift: event.shiftKey,
  };
  for (const part of parts) {
    if (!metaChecks[part]) return false;
  }
  return event.key.toLowerCase() === key;
}
