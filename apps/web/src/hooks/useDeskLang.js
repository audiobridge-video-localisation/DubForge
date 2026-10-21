import { useSyncExternalStore } from "react";

// The language the hero desk is localized into. Lives outside React so the nav's
// language chip and the hero stay in sync without prop drilling.
let lang = "es";
const listeners = new Set();

const subscribe = (fn) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

export const useDeskLang = () => useSyncExternalStore(subscribe, () => lang);

export function setDeskLang(next) {
  if (next === lang) return;
  lang = next;
  listeners.forEach((fn) => fn());
}

// Ask the hero to run its "dubbing…" sequence for `next`.
export const requestDub = (next) =>
  globalThis.dispatchEvent(
    new globalThis.CustomEvent("dubforge:dub", { detail: next }),
  );

export function onDubRequest(handler) {
  const listener = (e) => handler(e.detail);
  globalThis.addEventListener("dubforge:dub", listener);
  return () => globalThis.removeEventListener("dubforge:dub", listener);
}
