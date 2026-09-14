import { useEffect, useLayoutEffect, useRef, useState } from "react";

// Every animation respects "reduce motion". Checked live so a system change applies immediately.
export function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Counts from 0 up to `target` with an ease-out curve. Re-runs only when the target changes. */
export function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));
  const from = useRef(0);
  useEffect(() => {
    if (prefersReducedMotion() || !Number.isFinite(target)) {
      setValue(target);
      return undefined;
    }
    const start = performance.now();
    const origin = from.current;
    let frame;
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      setValue(Math.round(origin + (target - origin) * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
      else from.current = target;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

/**
 * Position of a pill that slides to the active item inside `containerRef`.
 * Returns a style for the indicator, or null before measurement. `ready` flips on after the
 * first measurement so the pill appears in place instead of sliding in from the left edge.
 */
export function useSlidingIndicator(containerRef, activeSelector, deps) {
  const [style, setStyle] = useState(null);
  const [ready, setReady] = useState(false);
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const measure = () => {
      const active = container.querySelector(activeSelector);
      if (!active) return setStyle(null);
      setStyle({ width: `${active.offsetWidth}px`, height: `${active.offsetHeight}px`,
                 transform: `translate(${active.offsetLeft}px, ${active.offsetTop}px)` });
    };
    measure();
    const frame = requestAnimationFrame(() => setReady(true));
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { style, ready };
}

/** A soft light that follows the pointer across the backdrop (mouse and trackpad only). */
export function useSpotlight(ref) {
  useEffect(() => {
    const el = ref.current;
    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    if (!el || !finePointer || prefersReducedMotion()) return undefined;
    let frame = 0;
    let x = window.innerWidth / 2;
    let y = window.innerHeight / 3;
    const paint = () => {
      frame = 0;
      el.style.setProperty("--spot-x", `${x}px`);
      el.style.setProperty("--spot-y", `${y}px`);
    };
    const onMove = (event) => {
      x = event.clientX;
      y = event.clientY;
      el.classList.add("on");
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const onLeave = () => el.classList.remove("on");
    paint();
    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, [ref]);
}
