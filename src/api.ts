import { callable } from "@decky/api";

export interface ParamSpec {
  key: string;
  label: string;
  type: "slider" | "color" | "toggle" | "select";
  default: unknown;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  options?: { value: string; label: string }[];
  show_if?: { key: string; op: "eq" | "ne" | "gte" | "in"; value: unknown }[];
}

export interface EffectSpec {
  id: string;
  label: string;
  description: string;
  params: ParamSpec[];
}

export interface Status {
  available: boolean;
  leds: number;
  enabled: boolean;
  effect: string;
  brightness: number;
  reverse: boolean;
  playing: string | null;
  params: Record<string, unknown>;
  now_playing: boolean;
  game_palette: string[] | null;
  game_palette_app_id: string | null;
}

export interface ProfileEntry {
  name: string;
  effect: string;
}

// ── read ──────────────────────────────────────────────────────────────────────

export const getStatus  = callable<[], Status>("get_status");
export const getCatalog = callable<[], EffectSpec[]>("get_catalog");
export const getParams  = callable<[effect_id: string], Record<string, unknown>>("get_params");

// ── control (return updated Status so the UI can refresh atomically) ──────────

export const setEnabled    = callable<[enabled: boolean], Status>("set_enabled");
export const setEffect     = callable<[effect_id: string], Status>("set_effect");
export const setParam      = callable<[effect_id: string, key: string, value: unknown], void>("set_param");
export const setBrightness = callable<[value: number], void>("set_brightness");
export const setReverse    = callable<[value: boolean], void>("set_reverse");
export const setNowPlaying = callable<[enabled: boolean], Status>("set_now_playing");

// ── game (called by startGameWatch at plugin scope) ───────────────────────────

export const gameChanged    = callable<[title: string, app_id?: string], void>("game_changed");
export const setGamePalette = callable<[colors: string[], app_id?: string], void>("set_game_palette");

// ── profiles ──────────────────────────────────────────────────────────────────

export const listProfiles  = callable<[], ProfileEntry[]>("list_profiles");
export const saveProfile   = callable<[name: string], boolean>("save_profile");
export const loadProfile   = callable<[name: string], boolean>("load_profile");
export const deleteProfile = callable<[name: string], boolean>("delete_profile");
