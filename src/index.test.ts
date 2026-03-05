import { beforeEach, describe, expect, it, vi } from "vitest";

const launchMock = vi.fn();
const TEST_API_KEY = "test-key";

vi.mock("@cloudflare/puppeteer", () => ({
  default: {
    launch: launchMock
  }
}));

const { default: worker } = await import("./index");

describe("social pipeline worker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects preview requests without API key", async () => {
    const response = await worker.fetch(
      new Request("https://worker.test/template/instagram-portrait?title=Hello&caption=World"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(401);
  });

  it("renders template endpoint without CDN script and with token variables", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template/instagram-portrait?title=Hello&caption=World&brandingColor=%230a8fa5"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain("--color-text-primary");
    expect(html).toContain("<style>");
    expect(html).not.toContain("@tailwindcss/browser");
    expect(html).not.toContain("1080 x 1080");
  });

  it("hides carousel labels by default", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template/carousel-post?title=T&heading=H&body=B&slide=1&total=5"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).not.toContain("SLIDE 1/5");
    expect(html).not.toContain("CAROUSEL");
  });

  it("resolves preview templates with slot values", async () => {
    const response = await worker.fetch(
      authorizedRequest(
        "https://worker.test/template/instagram-portrait?templateId=core/metric-card&slot.metric_value=9.8K&slot.metric_label=Engagement&slot.headline=Signal+that+compounds"
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain('data-template-id="core/metric-card"');
    expect(html).not.toContain("data-template-archetype=");
    expect(html).toContain("9.8K");
    expect(html).toContain("Signal that compounds");
  });

  it("applies font variables from css-based template head", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template/twitter-card?title=Data&caption=Point"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain("--font-display:");
    expect(html).toContain("--font-body:");
  });

  it("does not render style-specific css classes", async () => {
    const response = await worker.fetch(
      authorizedRequest(
        "https://worker.test/template/twitter-card?templateId=core/bold-base&title=Data+Story&caption=Signal+beats+noise"
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).not.toContain("style-data");
  });

  it("returns template catalog with template versions", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template-catalog"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      ok: boolean;
      schema_version: number;
      catalog_version: string;
      templates: Array<{ id: string; version: string }>;
      templates_by_format: Record<string, string[]>;
    };

    expect(body.ok).toBe(true);
    expect(body.schema_version).toBe(1);
    expect(typeof body.catalog_version).toBe("string");
    expect(body.templates.length).toBeGreaterThan(0);
    expect(body.templates[0].version.length).toBeGreaterThan(0);
    expect(body.templates_by_format["instagram-portrait"].length).toBeGreaterThan(0);
  });

  it("generates assets from direct plain-content endpoint", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "Quick practical update for your workflow.",
            twitter_caption: "Actionable workflow update in one pass.",
            linkedin_caption: "A clear process to streamline your content pipeline.",
            carousel_slides: [
              { heading: "Start", body: "Define your post objective before drafting." },
              { heading: "Extract", body: "Pull key points from the source article." },
              { heading: "Design", body: "Map each point into a visual format." },
              { heading: "Render", body: "Generate every platform dimension automatically." },
              { heading: "Ship", body: "Publish and review performance outcomes." }
            ],
            hashtags: [
              "#workflow",
              "#contentops",
              "#socialmedia",
              "#cloudflare",
              "#ghostcms",
              "#automation",
              "#creator",
              "#pipeline"
            ],
            image_prompt: "A clean workspace with a laptop and notes, editorial style",
            use_feature_image: true,
            slot_content: {
              headline: "Build repeatable systems",
              insight_line: "Consistency compounds when your process is simple."
            }
          })
        }))
      },
      BROWSER: {},
      OUTPUT_BUCKET: {
        put: vi.fn(async () => null)
      },
      API_KEYS: TEST_API_KEY,
      DEFAULT_BRAND_COLOR: "#1f7a8c",
      BRAND_NAME: "Tasbir Blog",
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const response = await worker.fetch(
      authorizedRequest("https://worker.test/generate-from-content", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: "Test Pipeline Post",
          content: "This is plain content used for local endpoint testing.",
          feature_image: "https://example.com/feature.jpg",
          slug: "test-pipeline-post"
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      ok: boolean;
      slug: string;
      image_source: { source: string };
      assets: { instagram_portrait: { key: string } };
    };

    expect(body.ok).toBe(true);
    expect(body.slug).toBe("test-pipeline-post");
    expect(body.image_source.source).toBe("feature");
    expect(body.assets.instagram_portrait.key).toContain("instagram-portrait.png");
  });

  it("supports selecting specific output formats from API", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "Quick practical update for your workflow.",
            twitter_caption: "Actionable workflow update in one pass.",
            linkedin_caption: "A clear process to streamline your content pipeline.",
            carousel_slides: [
              { heading: "Start", body: "Define your post objective before drafting." },
              { heading: "Extract", body: "Pull key points from the source article." },
              { heading: "Design", body: "Map each point into a visual format." },
              { heading: "Render", body: "Generate every platform dimension automatically." },
              { heading: "Ship", body: "Publish and review performance outcomes." }
            ],
            hashtags: ["#workflow", "#contentops", "#socialmedia", "#cloudflare", "#automation", "#creator", "#pipeline", "#growth"],
            image_prompt: "A clean workspace with a laptop and notes, editorial style",
            use_feature_image: true,
            slot_content: {
              headline: "Build repeatable systems",
              insight_line: "Consistency compounds when your process is simple."
            }
          })
        }))
      },
      BROWSER: {},
      OUTPUT_BUCKET: {
        put: vi.fn(async () => null)
      },
      API_KEYS: TEST_API_KEY,
      DEFAULT_BRAND_COLOR: "#1f7a8c",
      BRAND_NAME: "Tasbir Blog",
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const response = await worker.fetch(
      authorizedRequest("https://worker.test/generate-from-content", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: "Format Selection Test",
          content: "Generate only the Twitter card from this content.",
          feature_image: "https://example.com/feature.jpg",
          output: {
            formats: ["twitter-card"]
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      requested_formats: string[];
      assets: {
        instagram_portrait: unknown;
        instagram_square: unknown;
        instagram_story: unknown;
        twitter_card: { key: string } | null;
        linkedin_post: unknown;
        carousel: unknown[];
      };
    };

    expect(body.requested_formats).toEqual(["twitter-card"]);
    expect(body.assets.twitter_card?.key).toContain("twitter-card.png");
    expect(body.assets.instagram_portrait).toBeNull();
    expect(body.assets.instagram_square).toBeNull();
    expect(body.assets.instagram_story).toBeNull();
    expect(body.assets.linkedin_post).toBeNull();
    expect(body.assets.carousel).toHaveLength(0);
  });

  it("supports html-only visuals by disabling background image with image.mode none", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "Quick practical update for your workflow.",
            twitter_caption: "Actionable workflow update in one pass.",
            linkedin_caption: "A clear process to streamline your content pipeline.",
            carousel_slides: [
              { heading: "Start", body: "Define your post objective before drafting." },
              { heading: "Extract", body: "Pull key points from the source article." },
              { heading: "Design", body: "Map each point into a visual format." },
              { heading: "Render", body: "Generate every platform dimension automatically." },
              { heading: "Ship", body: "Publish and review performance outcomes." }
            ],
            hashtags: ["#workflow", "#contentops", "#socialmedia", "#cloudflare", "#automation", "#creator", "#pipeline", "#growth"],
            image_prompt: "A clean workspace with a laptop and notes, editorial style",
            use_feature_image: true,
            slot_content: {
              headline: "Build repeatable systems",
              insight_line: "Consistency compounds when your process is simple."
            }
          })
        }))
      },
      BROWSER: {},
      OUTPUT_BUCKET: {
        put: vi.fn(async () => null)
      },
      API_KEYS: TEST_API_KEY,
      DEFAULT_BRAND_COLOR: "#1f7a8c",
      BRAND_NAME: "Tasbir Blog",
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const response = await worker.fetch(
      authorizedRequest("https://worker.test/generate-from-content", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: "HTML-Only Visual Mode",
          content: "Use pure HTML decorative layers and skip external background images.",
          feature_image: "https://example.com/feature.jpg",
          image: {
            mode: "none"
          },
          output: {
            formats: ["instagram-portrait"]
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      image_source: { source: string };
      assets: { instagram_portrait: { key: string } | null };
    };

    expect(body.image_source.source).toBe("none");
    expect(body.assets.instagram_portrait?.key).toContain("instagram-portrait.png");
  });

  it("normalizes markdown captions and generic carousel headings", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "# Social Media Asset Pipeline Worker\n\nShip better content from one source.",
            twitter_caption: "## Social Media Asset Pipeline Worker\n\nShip better content from one source.",
            linkedin_caption: "# Social Media Asset Pipeline Worker\n\nShip better content from one source.",
            carousel_slides: [
              { heading: "Insight 1", body: "# Start from one source article and define a clear hook." },
              { heading: "Insight 2", body: "- Break the source into focused points for each platform." },
              { heading: "Insight 3", body: "## End with a clear next step the audience can apply today." }
            ],
            hashtags: ["#workflow", "#contentops", "#socialmedia", "#automation", "#cloudflare", "#pipeline", "#creator", "#growth"],
            image_prompt: "A clean desk and laptop in natural lighting",
            use_feature_image: false,
            slot_content: {}
          })
        }))
      },
      BROWSER: {},
      OUTPUT_BUCKET: {
        put: vi.fn(async () => null)
      },
      API_KEYS: TEST_API_KEY,
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const response = await worker.fetch(
      authorizedRequest("https://worker.test/generate-from-content", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: "Social Media Asset Pipeline Worker",
          content: "# Social Media Asset Pipeline Worker\n\nTurn one post into multi-platform outputs.",
          output: {
            formats: ["carousel-post"],
            carouselSlides: 3
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      llm_output: {
        instagram_caption: string;
        twitter_caption: string;
        linkedin_caption: string;
        carousel_slides: Array<{ heading: string; body: string }>;
      };
    };

    expect(body.llm_output.instagram_caption.startsWith("#")).toBe(false);
    expect(body.llm_output.twitter_caption.startsWith("#")).toBe(false);
    expect(body.llm_output.linkedin_caption.startsWith("#")).toBe(false);
    expect(body.llm_output.carousel_slides).toHaveLength(3);
    for (const slide of body.llm_output.carousel_slides) {
      expect(/^insight\s*\d*$/i.test(slide.heading)).toBe(false);
      expect(slide.body.length).toBeGreaterThan(0);
    }
  });

  it("returns 400 when plain-content payload misses required content", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/generate-from-content", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: "Incomplete payload" })
      }),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: string };
    expect(body.error).toContain("content");
  });
});

function authorizedRequest(input: string, init?: RequestInit): Request {
  const headers = new Headers(init?.headers ?? {});
  headers.set("x-api-key", TEST_API_KEY);
  return new Request(input, { ...init, headers });
}

function fakeBrowser() {
  const page = {
    setViewport: vi.fn(async () => undefined),
    setContent: vi.fn(async () => undefined),
    evaluate: vi.fn(async () => undefined),
    screenshot: vi.fn(async () => new Uint8Array([137, 80, 78, 71])),
    close: vi.fn(async () => undefined)
  };

  return {
    newPage: vi.fn(async () => page),
    close: vi.fn(async () => undefined)
  };
}

function fakeExecutionContext(): ExecutionContext {
  return {
    waitUntil: vi.fn(),
    passThroughOnException: vi.fn()
  } as unknown as ExecutionContext;
}
