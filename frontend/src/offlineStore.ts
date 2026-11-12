// Saves the offline journey card in IndexedDB on this device.
// The card from the backend already has a masked PNR and no names; we store nothing else.
import type { OfflineCard } from "./api";

const DB = "agla-kadam", STORE = "cards";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!("indexedDB" in window)) return reject(new Error("NO_INDEXEDDB"));
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result as T);
    req.onerror = () => reject(req.error);
  });
}

export interface SavedCard { card: OfflineCard; saved_at: string }

export const offlineStore = {
  save: (card: OfflineCard) => run<void>("readwrite", (s) => s.put({ card, saved_at: new Date().toISOString() }, card.journey_id)),
  get: (id: string) => run<SavedCard | undefined>("readonly", (s) => s.get(id)),
  remove: (id: string) => run<void>("readwrite", (s) => s.delete(id)),
};
