// A minimal hash router: the console is a handful of pages, and hash URLs work
// unchanged when demo_api.py serves the built files (no server rewrite rules).
//
//   #/ask                 ask screen           #/ask/<sourceId>  with a source
//   #/admin               dashboard            #/admin/sources   data sources
//   #/admin/sources/<id>  one data source      #/admin/configuration
//   #/admin/activity

import { useEffect, useState } from "react";

function current() {
  const raw = (typeof window !== "undefined" && window.location.hash) || "";
  return raw.replace(/^#/, "") || "/ask";
}

export function parseRoute(path) {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "admin") {
    const page = parts[1] || "dashboard";
    return { area: "admin", page, id: parts[2] ? decodeURIComponent(parts[2]) : null };
  }
  return { area: "ask", page: "ask", id: parts[1] ? decodeURIComponent(parts[1]) : null };
}

export function useRoute() {
  const [path, setPath] = useState(current);
  useEffect(() => {
    const onChange = () => {
      setPath(current());
      window.scrollTo?.(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return parseRoute(path);
}

export function go(path) {
  window.location.hash = path;
}

export const href = (path) => `#${path}`;
