/**
 * K-means colour quantizer for Steam artwork.
 *
 * Runs entirely in the browser (no external deps) and produces 4-6 vivid
 * colours suitable for driving the LED bar.
 *
 * Usage:
 *   const colors = await extractPalette(appId, 6);
 *   // returns string[] of hex colors like ["FF1744", "00FFCC", ...]
 */

const STEAM_HEADER_URL = (appId: string) =>
  `https://cdn.steamcommunity.com/apps/${appId}/header.jpg`;

/** Draw a Steam header image to an offscreen canvas and return pixel data. */
async function fetchPixels(appId: string): Promise<Uint8ClampedArray | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      // Scale down to 10% — enough colour samples, tiny memory footprint.
      const W = Math.max(1, Math.round(img.naturalWidth * 0.1));
      const H = Math.max(1, Math.round(img.naturalHeight * 0.1));
      const canvas = document.createElement("canvas");
      canvas.width = W;
      canvas.height = H;
      const ctx = canvas.getContext("2d");
      if (!ctx) { resolve(null); return; }
      ctx.drawImage(img, 0, 0, W, H);
      resolve(ctx.getImageData(0, 0, W, H).data);
    };
    img.onerror = () => resolve(null);
    img.src = STEAM_HEADER_URL(appId);
  });
}

type RGB = [number, number, number];

/** Filter out pixels that are too dark or too light to show on LEDs. */
function usablePixels(data: Uint8ClampedArray): RGB[] {
  const out: RGB[] = [];
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    // Skip near-black (dim on LEDs) and near-white (looks washed out).
    if (r < 30 && g < 30 && b < 30) continue;
    if (r > 225 && g > 225 && b > 225) continue;
    out.push([r, g, b]);
  }
  return out;
}

/** Euclidean squared distance in RGB space. */
function dist2(a: RGB, b: RGB): number {
  return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
}

/** K-means clustering — 5 iterations is plenty at thumbnail resolution. */
function kmeans(pixels: RGB[], k: number, iterations = 5): RGB[] {
  if (pixels.length === 0) return [];
  k = Math.min(k, pixels.length);

  // Initialise centroids by picking evenly-spaced samples (deterministic).
  const step = Math.floor(pixels.length / k);
  let centroids: RGB[] = Array.from({ length: k }, (_, i) =>
    [...pixels[i * step]] as RGB
  );

  for (let iter = 0; iter < iterations; iter++) {
    const sums: [number, number, number, number][] = Array.from(
      { length: k },
      () => [0, 0, 0, 0]
    );
    for (const px of pixels) {
      let nearest = 0, best = Infinity;
      for (let j = 0; j < k; j++) {
        const d = dist2(px, centroids[j]);
        if (d < best) { best = d; nearest = j; }
      }
      sums[nearest][0] += px[0];
      sums[nearest][1] += px[1];
      sums[nearest][2] += px[2];
      sums[nearest][3]++;
    }
    centroids = sums.map(([r, g, b, n]) =>
      n > 0 ? [r / n, g / n, b / n] as RGB : [0, 0, 0] as RGB
    );
  }
  return centroids;
}

/** HSL saturation of an RGB triplet (0-255 scale). */
function saturation(rgb: RGB): number {
  const r = rgb[0] / 255, g = rgb[1] / 255, b = rgb[2] / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return 0;
  const d = max - min;
  return d / (l < 0.5 ? max + min : 2 - max - min);
}

/** Convert a float-scale RGB centroid to a hex string. */
function toHex(rgb: RGB): string {
  return rgb
    .map((c) => Math.min(255, Math.max(0, Math.round(c))).toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
}

/**
 * Extract dominant vivid colours from a game's Steam header artwork.
 *
 * @param appId  Steam numeric app ID (as a string).
 * @param count  How many colours to return (2-6).
 * @returns      Array of uppercase hex strings, or null on fetch failure.
 */
export async function extractPalette(
  appId: string,
  count = 6
): Promise<string[] | null> {
  const data = await fetchPixels(appId);
  if (!data) return null;

  const pixels = usablePixels(data);
  if (pixels.length < 2) return null;

  const centroids = kmeans(pixels, count);
  // Sort most saturated first — vivid colours look better on LEDs than grays.
  centroids.sort((a, b) => saturation(b) - saturation(a));

  // Require at least 2 reasonably distinct colours.
  const hexColors = centroids.map(toHex);
  if (hexColors.length < 2) return null;

  return hexColors;
}
