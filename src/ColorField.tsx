/**
 * HSV colour picker for Steam Deck Game Mode.
 *
 * Uses two sliders (hue + saturation) rather than a 2D wheel because
 * everything here must be driveable with a thumbstick and D-pad.
 * Brightness is omitted — the panel already has a global brightness control.
 */
import { SliderField } from "@decky/ui";
import React, { useEffect, useState } from "react";

interface Props {
  value: string;   // 6-char hex without #
  onChange: (hex: string) => void;
  label?: string;
}

function hexToHsv(hex: string): [number, number] {
  const r = parseInt(hex.slice(0, 2), 16) / 255;
  const g = parseInt(hex.slice(2, 4), 16) / 255;
  const b = parseInt(hex.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const d = max - min;
  let h = 0;
  if (d > 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h = (h / 6 + 1) % 1;
  }
  const s = max === 0 ? 0 : d / max;
  return [h, s];
}

function hsvToHex(h: number, s: number): string {
  // Fixed V=1 — the global brightness slider covers the value dimension.
  const v = 1.0;
  const i = Math.floor(h * 6);
  const f = h * 6 - i;
  const p = v * (1 - s);
  const q = v * (1 - f * s);
  const t = v * (1 - (1 - f) * s);
  let r = 0, g = 0, b = 0;
  switch (i % 6) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    case 5: r = v; g = p; b = q; break;
  }
  const toB = (x: number) =>
    Math.min(255, Math.max(0, Math.round(x * 255))).toString(16).padStart(2, "0");
  return `${toB(r)}${toB(g)}${toB(b)}`.toUpperCase();
}

export default function ColorField({ value, onChange, label = "Color" }: Props) {
  const [hue, setHue] = useState(0);
  const [sat, setSat] = useState(1);

  // Sync inward when parent changes the value (e.g. profile load).
  useEffect(() => {
    if (/^[0-9A-Fa-f]{6}$/.test(value)) {
      const [h, s] = hexToHsv(value);
      setHue(h);
      setSat(s);
    }
  }, [value]);

  const currentHex = hsvToHex(hue, sat);
  const swatch = `#${currentHex}`;

  function handleHue(v: number) {
    setHue(v);
    onChange(hsvToHex(v, sat));
  }

  function handleSat(v: number) {
    setSat(v);
    onChange(hsvToHex(hue, v));
  }

  return (
    <div style={{ padding: "4px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 4,
            background: swatch,
            border: "1px solid rgba(255,255,255,0.2)",
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 13, color: "rgba(255,255,255,0.7)" }}>{label}</span>
        <span
          style={{
            marginLeft: "auto",
            fontFamily: "monospace",
            fontSize: 12,
            color: "rgba(255,255,255,0.5)",
          }}
        >
          #{currentHex}
        </span>
      </div>
      <SliderField
        label="Hue"
        value={hue}
        min={0}
        max={1}
        step={0.005}
        onChange={handleHue}
      />
      <SliderField
        label="Saturation"
        value={sat}
        min={0}
        max={1}
        step={0.01}
        onChange={handleSat}
      />
    </div>
  );
}
