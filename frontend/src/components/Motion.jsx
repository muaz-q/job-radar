import { useRef } from "react";
import { useCountUp, useSlidingIndicator } from "../hooks/useMotion";

/** Large title whose words rise from behind a mask, one after another. */
export function RevealTitle({ as: Tag = "h1", className = "large-title", children }) {
  const words = String(children).split(" ");
  return (
    <Tag className={`${className} reveal`} aria-label={String(children)}>
      {words.map((word, i) => (
        <span key={i} className="reveal-mask" aria-hidden="true">
          <span className="reveal-word" style={{ "--d": `${i * 70}ms` }}>{word}</span>
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </Tag>
  );
}

/** Animated number (ease-out count-up). */
export function CountUp({ value }) {
  const shown = useCountUp(value);
  return <>{shown.toLocaleString()}</>;
}

/** iOS segmented control with a thumb that slides between options. */
export function Segmented({ options, value, onChange, label, role = "tablist", className = "" }) {
  const ref = useRef(null);
  const { style, ready } = useSlidingIndicator(ref, "button.active", [value, options.length]);
  const itemRole = role === "radiogroup" ? "radio" : "tab";
  return (
    <div ref={ref} className={`seg ${className}`} role={role} aria-label={label}>
      {style && <span className={ready ? "seg-thumb ready" : "seg-thumb"} style={style} aria-hidden="true" />}
      {options.map(([key, text]) => (
        <button key={key} type="button" role={itemRole}
                aria-selected={itemRole === "tab" ? value === key : undefined}
                aria-checked={itemRole === "radio" ? value === key : undefined}
                className={value === key ? "active" : ""} onClick={(event) => onChange(key, event)}>
          {text}
        </button>
      ))}
    </div>
  );
}
