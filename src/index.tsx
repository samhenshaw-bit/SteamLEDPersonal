import {
  definePlugin,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  staticClasses,
} from "@decky/ui";
import React, { useEffect, useState } from "react";
import { FaLightbulb } from "react-icons/fa";

import {
  getCatalog,
  getStatus,
  setBrightness,
  setEffect,
  setEnabled,
  setNowPlaying,
  setParam,
  setReverse,
  setGamePalette,
  gameChanged,
  type EffectSpec,
  type ParamSpec,
  type Status,
} from "./api";

import ColorField from "./ColorField";
import { extractPalette } from "./colorQuant";

// ── show_if evaluation ────────────────────────────────────────────────────────

function evalCondition(
  cond: { key: string; op: string; value: unknown },
  params: Record<string, unknown>
): boolean {
  const v = params[cond.key];
  switch (cond.op) {
    case "eq":  return v === cond.value;
    case "ne":  return v !== cond.value;
    case "gte": return typeof v === "number" && v >= (cond.value as number);
    case "in":  return Array.isArray(cond.value) && cond.value.includes(v);
    default:    return true;
  }
}

function paramVisible(spec: ParamSpec, params: Record<string, unknown>): boolean {
  if (!spec.show_if) return true;
  return spec.show_if.every((c) => evalCondition(c, params));
}

// ── param control ─────────────────────────────────────────────────────────────

function ParamControl({
  spec,
  value,
  effectId,
  onChange,
}: {
  spec: ParamSpec;
  value: unknown;
  effectId: string;
  onChange: (key: string, val: unknown) => void;
}) {
  async function send(val: unknown) {
    onChange(spec.key, val);
    await setParam(effectId, spec.key, val);
  }

  if (spec.type === "slider") {
    const unit = spec.unit ?? "";
    return (
      <PanelSectionRow>
        <SliderField
          label={`${spec.label}${unit ? ` (${unit})` : ""}`}
          value={(value as number) ?? (spec.default as number)}
          min={spec.min ?? 0}
          max={spec.max ?? 1}
          step={spec.step ?? 0.1}
          onChange={send}
        />
      </PanelSectionRow>
    );
  }

  if (spec.type === "toggle") {
    return (
      <PanelSectionRow>
        <ToggleField
          label={spec.label}
          checked={(value as boolean) ?? (spec.default as boolean)}
          onChange={send}
        />
      </PanelSectionRow>
    );
  }

  if (spec.type === "color") {
    return (
      <PanelSectionRow>
        <ColorField
          label={spec.label}
          value={(value as string) ?? (spec.default as string) ?? "FF3030"}
          onChange={(hex) => send(hex)}
        />
      </PanelSectionRow>
    );
  }

  if (spec.type === "select") {
    return (
      <PanelSectionRow>
        <DropdownItem
          label={spec.label}
          rgOptions={(spec.options ?? []).map((o) => ({
            data: o.value,
            label: o.label,
          }))}
          selectedOption={value ?? spec.default}
          onChange={(opt) => send(opt.data)}
        />
      </PanelSectionRow>
    );
  }

  return null;
}

// ── palette preview ───────────────────────────────────────────────────────────

function PaletteStrip({ colors }: { colors: string[] }) {
  if (!colors || colors.length === 0) return null;
  return (
    <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", margin: "4px 0", gap: 1 }}>
      {colors.map((hex, i) => (
        <div key={i} style={{ flex: 1, background: `#${hex}` }} />
      ))}
    </div>
  );
}

// ── game watch — called at PLUGIN scope, not inside a React hook ──────────────
//
// RegisterForAppLifetimeNotifications must be registered outside of React's
// lifecycle. Registering inside useEffect causes Decky Loader to crash on
// dismount because the unregister callback is never called before the plugin
// frame is torn down.

type PaletteHandler = (colors: string[] | null, appId: string | null) => void;
const _paletteHandlers = new Set<PaletteHandler>();
const _paletteCache = new Map<string, string[]>();

function startGameWatch(): () => void {
  let last: string | null = null;

  const report = async (title: string, appId: string | null) => {
    const key = appId ?? "";
    if (key === last) return;
    last = key;

    // Tell the backend which game is running (enables curated palette fallback).
    gameChanged(title || "", appId ?? undefined).catch((e) =>
      console.warn("[SteamLED] gameChanged", e)
    );

    if (!appId || !title) {
      for (const h of _paletteHandlers) h(null, null);
      setGamePalette([], undefined).catch(() => {});
      return;
    }

    // Serve from cache if we've already processed this game.
    if (_paletteCache.has(appId)) {
      const cached = _paletteCache.get(appId)!;
      for (const h of _paletteHandlers) h(cached, appId);
      setGamePalette(cached, appId).catch(() => {});
      return;
    }

    // Extract palette from Steam artwork via canvas k-means.
    try {
      const colors = await extractPalette(appId, 6);
      if (colors && colors.length >= 2) {
        _paletteCache.set(appId, colors);
        for (const h of _paletteHandlers) h(colors, appId);
        setGamePalette(colors, appId).catch(() => {});
      } else {
        for (const h of _paletteHandlers) h(null, appId);
      }
    } catch (e) {
      console.warn("[SteamLED] palette extract", e);
      for (const h of _paletteHandlers) h(null, appId);
    }
  };

  // Primary: app lifetime notifications — registered here, at plugin scope.
  let unregister: (() => void) | undefined;
  try {
    const reg = SteamClient?.GameSessions?.RegisterForAppLifetimeNotifications;
    if (typeof reg === "function") {
      const h = reg((u: any) => {
        if (u?.bRunning) {
          report(u?.strDisplayName ?? u?.strAppName ?? "", String(u.unAppID));
        } else {
          report("", null);
        }
      });
      unregister = () => h?.unregister?.();
    }
  } catch (e) {
    console.warn("[SteamLED] app lifetime hook unavailable", e);
  }

  // Fallback: poll Router.MainRunningApp every 4 s.
  const poll = setInterval(() => {
    try {
      const app = (window as any).Router?.MainRunningApp;
      if (app) {
        report(app.display_name ?? "", String(app.appid));
      } else if (last !== "") {
        report("", null);
      }
    } catch {}
  }, 4000);

  return () => {
    unregister?.();
    clearInterval(poll);
  };
}

// ── main content component ────────────────────────────────────────────────────

function Content() {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<Status | null>(null);
  const [catalog, setCatalog] = useState<EffectSpec[]>([]);
  const [localParams, setLocalParams] = useState<Record<string, unknown>>({});
  const [extractedPalette, setExtractedPalette] = useState<string[] | null>(null);
  const [detectedAppId, setDetectedAppId] = useState<string | null>(null);

  // Subscribe to palette updates pushed from the plugin-scope game watch.
  useEffect(() => {
    const handler: PaletteHandler = (colors, appId) => {
      setExtractedPalette(colors);
      setDetectedAppId(appId);
    };
    _paletteHandlers.add(handler);
    return () => { _paletteHandlers.delete(handler); };
  }, []);

  // Initial load + periodic refresh.
  useEffect(() => {
    const load = async () => {
      try {
        const [s, c] = await Promise.all([getStatus(), getCatalog()]);
        setStatus(s);
        setCatalog(c);
        setLocalParams(s.params ?? {});
      } catch (e) {
        console.warn("[SteamLED] load", e);
      }
      setLoading(false); // always clear loading, even if the call failed
    };
    load();
    const t = setInterval(async () => {
      try {
        const s = await getStatus();
        if (s) { setStatus(s); setLocalParams((p) => ({ ...(s.params ?? {}), ...p })); }
      } catch {}
    }, 3000);
    return () => clearInterval(t);
  }, []);

  function updateLocalParam(key: string, val: unknown) {
    setLocalParams((prev) => ({ ...prev, [key]: val }));
  }

  if (loading) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>
            Loading…
          </span>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  if (!status?.available) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>
            No light bar found. This plugin only works on Steam Machine hardware.
          </span>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  const currentSpec = catalog.find((e) => e.id === status.effect);
  const params: Record<string, unknown> = {
    ...(currentSpec?.params.reduce<Record<string, unknown>>((acc, p) => {
      acc[p.key] = p.default;
      return acc;
    }, {}) ?? {}),
    ...localParams,
  };
  const nowPlaying = status.now_playing ?? false;

  return (
    <>
      <PanelSection title="Light Bar">
        <PanelSectionRow>
          <ToggleField
            label="Enabled"
            checked={status.enabled}
            onChange={async (v) => {
              setStatus((s) => s ? { ...s, enabled: v } : s);
              await setEnabled(v);
            }}
          />
        </PanelSectionRow>

        {status.enabled && (
          <>
            <PanelSectionRow>
              <DropdownItem
                label="Effect"
                rgOptions={catalog.map((e) => ({ data: e.id, label: e.label }))}
                selectedOption={status.effect}
                onChange={async (opt) => {
                  const id = opt.data as string;
                  setStatus((s) => s ? { ...s, effect: id } : s);
                  try { const s = await setEffect(id); if (s) { setStatus(s); setLocalParams(s.params ?? {}); } } catch {}
                }}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <SliderField
                label="Brightness"
                value={status.brightness ?? 1}
                min={0}
                max={1}
                step={0.01}
                onChange={async (v) => {
                  setStatus((s) => s ? { ...s, brightness: v } : s);
                  await setBrightness(v);
                }}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Reverse direction"
                checked={status.reverse ?? false}
                onChange={async (v) => {
                  setStatus((s) => s ? { ...s, reverse: v } : s);
                  await setReverse(v);
                }}
              />
            </PanelSectionRow>
          </>
        )}
      </PanelSection>

      {status.enabled && currentSpec && (
        <PanelSection title={currentSpec.label}>
          {currentSpec.params
            .filter((spec) => paramVisible(spec, params))
            .map((spec) => (
              <ParamControl
                key={spec.key}
                spec={spec}
                value={params[spec.key]}
                effectId={status.effect}
                onChange={updateLocalParam}
              />
            ))}
        </PanelSection>
      )}

      {status.enabled && (
        <PanelSection title="Now Playing">
          <PanelSectionRow>
            <ToggleField
              label="Match game colours"
              description="Extracts colours from each game's artwork automatically"
              checked={nowPlaying}
              onChange={async (v) => {
                setStatus((s) => s ? { ...s, now_playing: v } : s);
                await setNowPlaying(v);
                if (!v) { setExtractedPalette(null); setDetectedAppId(null); }
              }}
            />
          </PanelSectionRow>

          {nowPlaying && (
            <>
              {detectedAppId && (
                <PanelSectionRow>
                  <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}>
                    App ID: {detectedAppId}
                  </span>
                </PanelSectionRow>
              )}
              {extractedPalette && extractedPalette.length > 0 ? (
                <PanelSectionRow>
                  <div>
                    <span style={{ display: "block", fontSize: 12, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>
                      Extracted palette
                    </span>
                    <PaletteStrip colors={extractedPalette} />
                  </div>
                </PanelSectionRow>
              ) : detectedAppId ? (
                <PanelSectionRow>
                  <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>
                    Using curated palette or current effect
                  </span>
                </PanelSectionRow>
              ) : (
                <PanelSectionRow>
                  <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>
                    Launch a game to activate
                  </span>
                </PanelSectionRow>
              )}
            </>
          )}
        </PanelSection>
      )}
    </>
  );
}

// ── plugin registration ───────────────────────────────────────────────────────

export default definePlugin(() => {
  // startGameWatch must be called here — outside React — so that
  // RegisterForAppLifetimeNotifications is registered once at plugin load
  // and its cleanup runs reliably in onDismount.
  const stopWatch = startGameWatch();

  return {
    name: "SteamLED",
    titleView: <div className={staticClasses.Title}>SteamLED</div>,
    content: <Content />,
    icon: <FaLightbulb />,
    onDismount() {
      stopWatch();
    },
  };
});
