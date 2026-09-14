import { useCallback, useEffect, useState } from "react";

// Appearance: "system" follows the device; "light"/"dark" are explicit choices.
// The choice lives in this browser only (it is a per-device preference, not a setting to sync).
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

export function useTheme() {
  const [choice, setChoice] = useState(readChoice);
  const [systemDark, setSystemDark] = useState(() => Boolean(media?.matches));

  useEffect(() => {
    if (!media) return undefined;
    const onChange = (event) => setSystemDark(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const resolved = choice === "system" ? (systemDark ? "dark" : "light") : choice;

  useEffect(() => {
    const root = document.documentElement;
    if (choice === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", choice);
    try {
      if (choice === "system") window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, choice);
    } catch {
      // private browsing: the choice still applies for this visit
    }
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", resolved === "dark" ? "#07070C" : "#F4F3F8");
  }, [choice, resolved]);

  // The header button flips between light and dark explicitly.
  const toggle = useCallback(() => setChoice((current) => (resolve(current) === "dark" ? "light" : "dark")), []);

  return { choice, resolved, setChoice, toggle };
}
