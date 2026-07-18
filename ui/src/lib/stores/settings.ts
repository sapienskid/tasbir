import { writable } from "svelte/store";
import { getSettings, type Settings } from "$lib/api/settings";

interface SettingsState {
  data: Settings | null;
  loading: boolean;
  error: string | null;
}

function createSettingsStore() {
  const { subscribe, update } = writable<SettingsState>({
    data: null,
    loading: false,
    error: null,
  });

  return {
    subscribe,
    async load() {
      update((s) => ({ ...s, loading: true, error: null }));
      try {
        const res = await getSettings();
        update((s) => ({ ...s, data: res.data, loading: false }));
      } catch (e) {
        update((s) => ({
          ...s,
          loading: false,
          error: e instanceof Error ? e.message : "Failed to load settings",
        }));
      }
    },
  };
}

export const settingsStore = createSettingsStore();
