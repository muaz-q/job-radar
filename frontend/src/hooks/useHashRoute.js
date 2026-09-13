import { useEffect, useState } from "react";

// A tiny hash router: "#/jobs/12" -> { page: "jobs", id: "12" }.
// Five screens don't need a routing library.
function parse(hash) {
  const [page = "jobs", id = null] = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { page, id };
}

export function useHashRoute() {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export function navigate(path) {
  window.location.hash = path;
}
