import { useState } from "react";

// Muted system colours for the initial shown when a company has no usable logo.
const INITIAL_COLORS = ["#0A84FF", "#30B0C7", "#34C759", "#FF9500", "#FF2D55", "#AF52DE", "#5856D6", "#A2845E"];

function colorFor(name) {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return INITIAL_COLORS[hash % INITIAL_COLORS.length];
}

function safeLogo(url) {
  try {
    return new URL(url).protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

// Site icons (Google favicons) are small squares on transparency; source photos fill the tile.
const isSiteIcon = (url) => url.includes("google.com/s2/favicons");

export default function CompanyLogo({ company = "", url, size = 48 }) {
  const [failed, setFailed] = useState(false);
  const src = safeLogo(url);
  const style = { "--size": `${size}px` };

  if (!src || failed) {
    const letter = (company.trim()[0] || "?").toUpperCase();
    return (
      <span className="logo initial" style={{ ...style, background: colorFor(company) }} aria-hidden="true">
        {letter}
      </span>
    );
  }
  return (
    <span className={isSiteIcon(src) ? "logo" : "logo fill"} style={style} aria-hidden="true">
      <img src={src} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer"
           onError={() => setFailed(true)} />
    </span>
  );
}
