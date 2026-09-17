/**
 * Type-safe RPC bindings for the SteamLED Python backend.
 *
 * All calls go through Decky's serverAPI.callPluginMethod(), which handles
 * the IPC bridge. Never call fetch() or WebSocket directly.
 */
import { callable } from "@decky/api";

// ── types ─────────────────────────────────────────────────────────────────────

export interface ParamSpec {
  key: string;
  label: string;
  type: "slider" | "color" | "toggle" | "select";
  default: unknown;
  // slider
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  // select
  options?: { value: string; label: string }[];
  // conditional visibility
  show_if?: { key: string; op: "eq" | "ne" | "gte" | "in"; value: unknown }[];
}

export interface EffectSpec {
  id: string;
  label: string;
  description: string;
  params: ParamSpec[];
}

export interface Status {
  enabled: boolean;
  effect: string;
  brightness: number;
  reverse: boolean;
  now_playing: boolean;
  params: Record<string, unknown>;
  game_palette: string[] | null;
  game_palette_app_id: string | null;
  hardware: boolean;
}

export interface ProfileEntry {
  name: string;
  effect: string;
}

// ── read ──────────────────────────────────────────────────────────────────────

export const getStatus    = callable<[], Status>("get_status");
export const getCatalog   = callable<[], EffectSpec[]>("get_catalog");
export const getParams    = callable<[effect_id: string], Record<string, unknown>>("get_params");
export const listProfiles = callable<[], ProfileEntry[]>("list_profiles");

// ── control ───────────────────────────────────────────────────────────────────

export const setEnabled    = callable<[enabled: boolean], void>("set_enabled");
export const setEffect     = callable<[effect_id: string], void>("set_effect");
export const setParam      = callable<[effect_id: string, key: string, value: unknown], void>("set_param");
export const setBrightness = callable<[value: number], void>("set_brightness");
export const setReverse    = callable<[value: boolean], void>("set_reverse");
export const setNowPlaying = callable<[enabled: boolean], void>("set_now_playing");

// ── game palette ──────────────────────────────────────────────────────────────

export const setGamePalette = callable<[colors: string[], app_id?: string], void>("set_game_palette");
export const gameChanged    = callable<[title: string, app_id?: string], void>("game_changed");

// ── profiles ──────────────────────────────────────────────────────────────────

export const saveProfile   = callable<[name: string], boolean>("save_profile");
export const loadProfile   = callable<[name: string], boolean>("load_profile");
export const deleteProfile = callable<[name: string], boolean>("delete_profile");
