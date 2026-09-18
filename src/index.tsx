/**
 * SteamLED — main plugin panel.
 *
 * Additions over the original:
 *   - Dynamic game palette: on each game launch, fetches Steam header artwork
 *     and extracts colours via canvas k-means, then sends them to the backend.
 *   - Palette preview strip: small swatches showing the extracted colours.
 *   - Profile manager section for saving/loading effect snapshots.
 */
import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  Dropdown,
  ButtonItem,
  staticClasses,
} from "@decky/ui";
import { routerHook } from "@decky/api";
import React, { useCallback, useEffect, useRef, useState } from "react";
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
import ProfileManager from "./ProfileManager";
import { extractPalette } from "./colorQuant";

// ── palette preview ───────────────────────────────────────────────────────────

function PaletteStrip({ colors }: { colors: string[] }) {
  if (!colors || colors.length === 0) return null;
  return (
    <div
      style={{
        display: "flex",
        height: 8,
        borderRadius: 4,
        overflow: "hidden",
        margin: "4px 0",
        gap: 1,
      }}
    >
      {colors.map((hex, i) => (
        <div
          key={i}
          style={{ flex: 1, background: `#${hex}` }}
        />
      ))}
    </div>
  );
}

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

function paramVisible(
  spec: ParamSpec,
  params: Record<string, unknown>
): boolean {
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
          value={value as number ?? spec.default as number}
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
          checked={value as boolean ?? spec.default as boolean}
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
        <Dropdown
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

// ── game watch ────────────────────────────────────────────────────────────────

/** Cache of appId → extracted palette so we don't re-fetch on each launch. */
const paletteCache = new Map<string, string[]>();

function useGameWatch(
  nowPlaying: boolean,
  onPaletteExtracted: (colors: string[] | null, appId: string | null) => void
) {
  const currentAppId = useRef<string | null>(null);

  const handleGameChange = useCallback(
    async (title: string | null, appId: string | null) => {
      if (appId === currentAppId.current) return;
      currentAppId.current = appId;

      // Notify backend of game change (enables curated palette fallback).
      await gameChanged(title ?? "", appId ?? undefined);

      if (!title || !appId || !nowPlaying) {
        onPaletteExtracted(null, null);
        await setGamePalette([], appId ?? undefined);
        return;
      }

      // Check cache first.
      if (paletteCache.has(appId)) {
        const cached = paletteCache.get(appId)!;
        onPaletteExtracted(cached, appId);
        await setGamePalette(cached, appId);
        return;
      }

      // Extract palette from Steam artwork.
      const colors = await extractPalette(appId, 6);
      if (colors && colors.length >= 2) {
        paletteCache.set(appId, colors);
        onPaletteExtracted(colors, appId);
        await setGamePalette(colors, appId);
      } else {
        onPaletteExtracted(null, appId);
      }
    },
    [nowPlaying, onPaletteExtracted]
  );

  useEffect(() => {
    // Primary: app lifetime notifications.
    const unregister = SteamClient?.GameSessions?.RegisterForAppLifetimeNotifications?.(
      (evt: { bRunning: boolean; unAppID: number; strDisplayName: string }) => {
        if (evt.bRunning) {
          handleGameChange(evt.strDisplayName ?? null, String(evt.unAppID));
        } else {
          handleGameChange(null, null);
        }
      }
    );

    // Fallback: poll Router.MainRunningApp every 4s.
    const poll = setInterval(() => {
      const app = (window as any).Router?.MainRunningApp;
      if (app) {
        handleGameChange(app.display_name ?? null, String(app.appid));
      } else if (currentAppId.current !== null) {
        handleGameChange(null, null);
      }
    }, 4000);

    return () => {
      unregister?.();
      clearInterval(poll);
    };
  }, [handleGameChange]);
}

// ── main content component ────────────────────────────────────────────────────

function Content() {
  const [status, setStatus] = useState<Status | null>(null);
  const [catalog, setCatalog] = useState<EffectSpec[]>([]);
  const [localParams, setLocalParams] = useState<Record<string, unknown>>({});
  const [extractedPalette, setExtractedPalette] = useState<string[] | null>(null);
  const [detectedAppId, setDetectedAppId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Optimistic local parameter state for snappy UI response.
  function updateLocalParam(key: string, val: unknown) {
    setLocalParams((prev) => ({ ...prev, [key]: val }));
  }

  const refresh = useCallback(async () => {
    try {
      const s = await getStatus();
      if (s) {
        setStatus(s);
        setLoadError(null);
        setLocalParams(s.params ?? {});
        if (s.game_palette && s.game_palette.length > 0) {
          setExtractedPalette(s.game_palette);
        }
      }
    } catch (e) {
      setLoadError(`Backend error: ${e}`);
    }
    try {
      const c = await getCatalog();
      if (c) setCatalog(c);
    } catch (_) {
      // non-fatal — keep whatever catalog we have
    }
  }, []);

  // Poll while panel is open.
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [refresh]);

  const nowPlaying = status?.now_playing ?? false;

  const handlePaletteExtracted = useCallback(
    (colors: string[] | null, appId: string | null) => {
      setExtractedPalette(colors);
      setDetectedAppId(appId);
    },
    []
  );

  useGameWatch(nowPlaying, handlePaletteExtracted);

  if (!status) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>
            {loadError ?? "Loading…"}
          </span>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  if (!status.hardware) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>
            No LED hardware found. This plugin only works on Steam Machine hardware.
          </span>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  const currentSpec = catalog.find((e) => e.id === status.effect);
  const params = { ...(currentSpec?.params.reduce<Record<string, unknown>>((acc, p) => {
    acc[p.key] = p.default;
    return acc;
  }, {}) ?? {}), ...localParams };

  return (
    <>
      {/* ── Profile manager ── */}
      <ProfileManager onLoad={refresh} />

      {/* ── Light bar toggle ── */}
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
              <Dropdown
                label="Effect"
                rgOptions={catalog.map((e) => ({ data: e.id, label: e.label }))}
                selectedOption={status.effect}
                onChange={async (opt) => {
                  const id = opt.data as string;
                  setStatus((s) => s ? { ...s, effect: id } : s);
                  await setEffect(id);
                  await refresh();
                }}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <SliderField
                label="Brightness"
                value={status.brightness}
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
                checked={status.reverse}
                onChange={async (v) => {
                  setStatus((s) => s ? { ...s, reverse: v } : s);
                  await setReverse(v);
                }}
              />
            </PanelSectionRow>
          </>
        )}
      </PanelSection>

      {/* ── Effect parameters ── */}
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

      {/* ── Now Playing ── */}
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
                if (!v) {
                  setExtractedPalette(null);
                  setDetectedAppId(null);
                }
              }}
            />
          </PanelSectionRow>

          {nowPlaying && (
            <>
              {detectedAppId && (
                <PanelSectionRow>
                  <span
                    style={{
                      fontSize: 12,
                      color: "rgba(255,255,255,0.5)",
                    }}
                  >
                    App ID: {detectedAppId}
                  </span>
                </PanelSectionRow>
              )}

              {extractedPalette && extractedPalette.length > 0 ? (
                <PanelSectionRow>
                  <div>
                    <span
                      style={{
                        display: "block",
                        fontSize: 12,
                        color: "rgba(255,255,255,0.5)",
                        marginBottom: 4,
                      }}
                    >
                      Extracted palette
                    </span>
                    <PaletteStrip colors={extractedPalette} />
                  </div>
                </PanelSectionRow>
              ) : detectedAppId ? (
                <PanelSectionRow>
                  <span
                    style={{
                      fontSize: 12,
                      color: "rgba(255,255,255,0.4)",
                    }}
                  >
                    Using curated palette or current effect
                  </span>
                </PanelSectionRow>
              ) : (
                <PanelSectionRow>
                  <span
                    style={{
                      fontSize: 12,
                      color: "rgba(255,255,255,0.4)",
                    }}
                  >
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

export default definePlugin(() => ({
  name: "SteamLED",
  titleView: <div className={staticClasses.Title}>SteamLED</div>,
  content: <Content />,
  icon: <FaLightbulb />,
  onDismount() {},
}));
