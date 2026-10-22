import type { ExportKind } from "../api/client";

// The API has no "list exports" call, so the export jobs a user has started are
// remembered in this browser. That lets the dub player come back after a reload.
const KEY = "dubforge:exports:v1";

type Store = Record<string, Partial<Record<ExportKind, string>>>;

function read(): Store {
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? "{}") as Store;
  } catch {
    return {};
  }
}

function write(store: Store) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    // storage full or blocked: the player just won't survive a reload
  }
}

export function storedExportIds(
  mediaId: string,
): Partial<Record<ExportKind, string>> {
  return read()[mediaId] ?? {};
}

export function rememberExport(
  mediaId: string,
  kind: ExportKind,
  jobId: string,
) {
  const store = read();
  store[mediaId] = { ...store[mediaId], [kind]: jobId };
  write(store);
}

export function forgetExport(mediaId: string, kind: ExportKind) {
  const store = read();
  if (!store[mediaId]) return;
  delete store[mediaId][kind];
  write(store);
}
