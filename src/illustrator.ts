export type IllustrationTone = "default" | "dark";

export interface IllustrationOptions {
  width?: number;
  height?: number;
  tone?: IllustrationTone;
  seed?: string;
}

export interface IllustrationElement {
  elementClass: string;
}

const ACCENTS = ["#D40000", "#0038A8", "#007A3D", "#E06000", "#6B0FAD", "#00868A", "#C8006A", "#C8A800"];
const DEFAULT_WIDTH = 1200;
const DEFAULT_HEIGHT = 1200;
const SHAPE_TYPES = ["circle", "rect", "line", "triangle", "ring", "arc", "cross"] as const;
const ELEMENT_SHAPES = ["dot", "ring", "line", "square", "triangle"] as const;
const ELEMENT_POSITIONS = [
  "top-[10%] right-[8%]",
  "top-[14%] right-[14%]",
  "top-[18%] left-[10%]",
  "bottom-[14%] right-[10%]",
  "bottom-[16%] left-[10%]",
  "top-[48%] right-[7%]"
] as const;
const ELEMENT_ROTATIONS = ["rotate-0", "rotate-12", "-rotate-12", "rotate-45", "-rotate-45", "rotate-90"] as const;
const ELEMENT_STANDARD_SIZES = ["h-16 w-16", "h-20 w-20", "h-24 w-24", "h-28 w-28"] as const;
const ELEMENT_LINE_SIZES = ["h-[3px] w-20", "h-[4px] w-24", "h-[5px] w-28"] as const;
const ELEMENT_TRIANGLE_SIZES = [
  "h-0 w-0 border-l-[14px] border-r-[14px] border-b-[24px]",
  "h-0 w-0 border-l-[18px] border-r-[18px] border-b-[30px]",
  "h-0 w-0 border-l-[22px] border-r-[22px] border-b-[36px]"
] as const;
const ELEMENT_COLORS_DARK = ["text-white", "text-zinc-200", "text-red-400", "text-sky-400", "text-emerald-400", "text-amber-400"] as const;
const ELEMENT_COLORS_LIGHT = ["text-black", "text-zinc-800", "text-red-700", "text-blue-700", "text-emerald-700", "text-amber-700"] as const;

type ShapeType = (typeof SHAPE_TYPES)[number];

type RandomSource = () => number;

export function generateIllustrationDataUrl(options: IllustrationOptions = {}): string {
  const svg = generateIllustrationSvg(options);
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function generateIllustrationSvg(options: IllustrationOptions = {}): string {
  const width = clampNumber(options.width ?? DEFAULT_WIDTH, 320, 4096);
  const height = clampNumber(options.height ?? DEFAULT_HEIGHT, 320, 4096);
  const tone: IllustrationTone = options.tone === "dark" ? "dark" : "default";
  const seed = options.seed?.trim() || createRandomSeed();
  const random = createRng(hashSeed(seed));
  const accent = pick(random, ACCENTS);
  const foreground = tone === "dark" ? "#FFFFFF" : "#0D0D0D";
  const secondary = tone === "dark" ? "#D8D8D8" : "#303030";

  const layers: string[] = [];

  const guideOpacity = tone === "dark" ? 0.05 : 0.07;
  layers.push(renderGuides(width, height, foreground, guideOpacity));

  const shapeCount = Math.round(8 + random() * 8);
  for (let index = 0; index < shapeCount; index += 1) {
    const type = pick(random, SHAPE_TYPES);
    const useAccent = random() < 0.32;
    const color = useAccent ? accent : random() < 0.45 ? secondary : foreground;
    const opacity = clampNumber((tone === "dark" ? 0.52 : 0.42) + random() * 0.42, 0.12, 0.92);
    const strokeWidth = snap(2 + random() * 10, 0.5);
    const x = snap(random() * width, 1);
    const y = snap(random() * height, 1);
    layers.push(renderShape({ random, type, width, height, x, y, color, opacity, strokeWidth }));
  }

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" fill="none">`,
    ...layers,
    "</svg>"
  ].join("");
}

export function generateIllustrationElement(options: IllustrationOptions = {}): IllustrationElement {
  const tone: IllustrationTone = options.tone === "dark" ? "dark" : "default";
  const seed = options.seed?.trim() || createRandomSeed();
  const random = createRng(hashSeed(seed));
  const shape = pick(random, ELEMENT_SHAPES);
  const positionClass = pick(random, ELEMENT_POSITIONS);
  const rotationClass = pick(random, ELEMENT_ROTATIONS);
  const colorClass = tone === "dark"
    ? pick(random, ELEMENT_COLORS_DARK)
    : pick(random, ELEMENT_COLORS_LIGHT);

  let shapeClass = "";
  if (shape === "dot") {
    shapeClass = `${pick(random, ELEMENT_STANDARD_SIZES)} rounded-full bg-current`;
  } else if (shape === "ring") {
    shapeClass = `${pick(random, ELEMENT_STANDARD_SIZES)} rounded-full border-[3px] border-current bg-transparent`;
  } else if (shape === "line") {
    shapeClass = `${pick(random, ELEMENT_LINE_SIZES)} rounded-full bg-current`;
  } else if (shape === "square") {
    shapeClass = `${pick(random, ELEMENT_STANDARD_SIZES)} border-[3px] border-current bg-transparent`;
  } else {
    shapeClass = `${pick(random, ELEMENT_TRIANGLE_SIZES)} border-l-transparent border-r-transparent border-b-current`;
  }

  return {
    elementClass: `${positionClass} ${rotationClass} ${colorClass} ${shapeClass}`.replace(/\s+/g, " ").trim()
  };
}

function renderShape(args: {
  random: RandomSource;
  type: ShapeType;
  width: number;
  height: number;
  x: number;
  y: number;
  color: string;
  opacity: number;
  strokeWidth: number;
}): string {
  const { random, type, width, height, x, y, color, opacity, strokeWidth } = args;

  switch (type) {
    case "circle": {
      const radius = snap(22 + random() * Math.min(width, height) * 0.16, 1);
      const fill = random() < 0.44 ? color : "none";
      return `<circle cx="${x}" cy="${y}" r="${radius}" fill="${fill}" stroke="${color}" stroke-width="${fill === "none" ? strokeWidth : 0}" opacity="${opacity}"/>`;
    }

    case "rect": {
      const rectWidth = snap(42 + random() * width * 0.24, 1);
      const rectHeight = snap(20 + random() * height * 0.16, 1);
      const rx = snap(random() * 8, 1);
      const x0 = clampNumber(x - rectWidth / 2, 0, Math.max(0, width - rectWidth));
      const y0 = clampNumber(y - rectHeight / 2, 0, Math.max(0, height - rectHeight));
      const fill = random() < 0.52 ? color : "none";
      return `<rect x="${x0}" y="${y0}" width="${rectWidth}" height="${rectHeight}" rx="${rx}" fill="${fill}" stroke="${color}" stroke-width="${fill === "none" ? strokeWidth : 0}" opacity="${opacity}"/>`;
    }

    case "line": {
      const length = snap(80 + random() * Math.max(width, height) * 0.28, 1);
      const angle = random() * Math.PI * 2;
      const x1 = snap(x - Math.cos(angle) * (length / 2), 1);
      const y1 = snap(y - Math.sin(angle) * (length / 2), 1);
      const x2 = snap(x + Math.cos(angle) * (length / 2), 1);
      const y2 = snap(y + Math.sin(angle) * (length / 2), 1);
      return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round" opacity="${opacity}"/>`;
    }

    case "triangle": {
      const radius = snap(28 + random() * Math.min(width, height) * 0.16, 1);
      const rotation = random() * Math.PI * 2;
      const points = [0, 1, 2]
        .map((index) => {
          const angle = rotation + (index * (Math.PI * 2)) / 3;
          const px = snap(x + Math.cos(angle) * radius, 1);
          const py = snap(y + Math.sin(angle) * radius, 1);
          return `${px},${py}`;
        })
        .join(" ");
      const fill = random() < 0.4 ? color : "none";
      return `<polygon points="${points}" fill="${fill}" stroke="${color}" stroke-width="${fill === "none" ? strokeWidth : 0}" opacity="${opacity}"/>`;
    }

    case "ring": {
      const baseRadius = snap(18 + random() * Math.min(width, height) * 0.1, 1);
      const gap = snap(8 + random() * 14, 1);
      const count = Math.max(2, Math.round(2 + random() * 3));
      const circles = Array.from({ length: count }, (_item, index) => {
        const radius = baseRadius + index * gap;
        return `<circle cx="${x}" cy="${y}" r="${radius}" fill="none" stroke="${color}" stroke-width="${Math.max(1, strokeWidth * 0.5)}" opacity="${opacity}"/>`;
      }).join("");
      return `<g>${circles}</g>`;
    }

    case "arc": {
      const radius = snap(36 + random() * Math.min(width, height) * 0.14, 1);
      const startAngle = random() * Math.PI * 2;
      const sweep = (0.55 + random() * 0.85) * Math.PI;
      const x1 = snap(x + Math.cos(startAngle) * radius, 1);
      const y1 = snap(y + Math.sin(startAngle) * radius, 1);
      const x2 = snap(x + Math.cos(startAngle + sweep) * radius, 1);
      const y2 = snap(y + Math.sin(startAngle + sweep) * radius, 1);
      const largeArcFlag = sweep > Math.PI ? 1 : 0;
      return `<path d="M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round" fill="none" opacity="${opacity}"/>`;
    }

    case "cross": {
      const arm = snap(18 + random() * Math.min(width, height) * 0.08, 1);
      return `<g opacity="${opacity}"><line x1="${x - arm}" y1="${y}" x2="${x + arm}" y2="${y}" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round"/><line x1="${x}" y1="${y - arm}" x2="${x}" y2="${y + arm}" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round"/></g>`;
    }

    default:
      return "";
  }
}

function renderGuides(width: number, height: number, color: string, opacity: number): string {
  const guides: string[] = [];
  const columns = 6;
  const rows = 6;

  for (let index = 1; index < columns; index += 1) {
    const x = snap((width * index) / columns, 1);
    guides.push(`<line x1="${x}" y1="0" x2="${x}" y2="${height}" stroke="${color}" stroke-width="1" opacity="${opacity}"/>`);
  }

  for (let index = 1; index < rows; index += 1) {
    const y = snap((height * index) / rows, 1);
    guides.push(`<line x1="0" y1="${y}" x2="${width}" y2="${y}" stroke="${color}" stroke-width="1" opacity="${opacity}"/>`);
  }

  return `<g>${guides.join("")}</g>`;
}

function createRandomSeed(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
}

function hashSeed(value: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function createRng(seed: number): RandomSource {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), state | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pick<T>(random: RandomSource, values: readonly T[]): T {
  return values[Math.floor(random() * values.length)] as T;
}

function snap(value: number, precision: number): number {
  const factor = 1 / precision;
  return Math.round(value * factor) / factor;
}

function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, value));
}
