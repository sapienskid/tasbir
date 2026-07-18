import { writable } from "svelte/store";

function createAuthStore() {
  const stored = typeof localStorage !== "undefined" ? localStorage.getItem("apiKey") : null;
  const { subscribe, set } = writable<string>(stored || "");

  return {
    subscribe,
    setKey(key: string) {
      localStorage.setItem("apiKey", key);
      set(key);
    },
    clear() {
      localStorage.removeItem("apiKey");
      set("");
    },
  };
}

export const apiKey = createAuthStore();
