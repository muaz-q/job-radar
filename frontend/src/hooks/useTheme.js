import { useCallback, useEffect, useState } from "react";
import { flushSync } from "react-dom";
import { prefersReducedMotion } from "./useMotion";

// Appearance: "system" follows the device; "light"/"dark" are explicit choices.
// The choice lives in this browser only (a per-device preference, not a setting to sync).
const KEY = "job-radar-theme";
const media = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function readChoice() {
  try {
    const value = window.localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

const resolve = (choice) => (choice === "system" ? (media?.matches ? "dark" : "light") : choice);

// Applied synchronously, so a view transition captures the new theme in its "after" snapshot.
function applyToDocument(choice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
  try {
    if (choice === "system") window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, choice);
  } catch {
    // private browsing: the choice still applies for this visit
  }
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", resolve(choice) === "dark" ? "#07070C" : "#F4F3F8");
}

export function useTheme() {
  const [choice, setChoiceState] = useState(readChoice);
  const [systemDark, setSystemDark] = useState(() => Boolean(media?.matches));

  useEffect(() => {
    if (!media) return undefined;
    const onChange = (event) => {
      setSystemDark(event.matches);
      applyToDocument(readChoice());
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => { applyToDocument(choice); }, [choice]);

  const resolved = choice === "system" ? (systemDark ? "dark" : "light") : choice;

  /**
   * Change appearance. When the visible theme actually flips, the new one is revealed as a circle
   * growing from the pointer (View Transitions API). Falls back to an instant change.
   */
  const setChoice = useCallback((next, event) => {
    const flips = resolve(next) !== resolve(readChoice());
    const commit = () => {
      applyToDocument(next);
      flushSync(() => setChoiceState(next));
    };
    if (!flips || !document.startViewTransition || prefersReducedMotion()) {
      commit();
      return;
    }
    const x = event?.clientX ?? window.innerWidth - 60;
    const y = event?.clientY ?? 32;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const transition = document.startViewTransition(commit);
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 620, easing: "cubic-bezier(0.22, 1, 0.36, 1)", pseudoElement: "::view-transition-new(root)" },
      );
    }).catch(() => {});
  }, []);

  // The header button flips between light and dark explicitly.
  const toggle = useCallback((event) => {
    setChoice(resolve(readChoice()) === "dark" ? "light" : "dark", event);
  }, [setChoice]);

  return { choice, resolved, setChoice, toggle };
}
