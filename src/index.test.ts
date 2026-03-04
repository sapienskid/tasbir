import { beforeEach, describe, expect, it, vi } from "vitest";

const launchMock = vi.fn();

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

  it("renders template endpoint without CDN script and with token variables", async () => {
    const response = await worker.fetch(
      new Request("https://worker.test/template/instagram-post?title=Hello&caption=World&brandingColor=%230a8fa5"),
      {} as never,
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
      new Request("https://worker.test/template/carousel-slide?title=T&heading=H&body=B&slide=1&total=5"),
      {} as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).not.toContain("SLIDE 1/5");
    expect(html).not.toContain("CAROUSEL");
  });

  it("resolves preview templates with archetype and slot values", async () => {
    const response = await worker.fetch(
      new Request(
        "https://worker.test/template/instagram-post?templateStyle=data&templateId=instagram-post/stat-split&archetype=metric&slot.metric_value=9.8K&slot.metric_label=Engagement&slot.headline=Signal+that+compounds&slot.insight_line=One+metric+only+works+when+paired+with+context."
      ),
      {} as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain('data-template-id="instagram-post/stat-split"');
    expect(html).toContain('data-template-style="data"');
    expect(html).toContain('data-template-archetype="metric"');
    expect(html).toContain("9.8K");
    expect(html).toContain("Signal that compounds");
  });

  it("applies requested font profile from preview query", async () => {
    const response = await worker.fetch(
      new Request("https://worker.test/template/twitter-card?title=Data&caption=Point&fontProfile=data-mono"),
      {} as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain("IBM+Plex+Mono");
    expect(html).toContain('--font-body: "IBM Plex Mono", monospace;');
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
            template_style: "editorial",
            post_archetype: "insight",
            font_profile: "editorial-serif",
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
      DEFAULT_BRAND_COLOR: "#1f7a8c",
      BRAND_NAME: "Tasbir Blog",
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const response = await worker.fetch(
      new Request("https://worker.test/generate-from-content", {
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
      assets: { instagram_post: { key: string } };
    };

    expect(body.ok).toBe(true);
    expect(body.slug).toBe("test-pipeline-post");
    expect(body.image_source.source).toBe("feature");
    expect(body.assets.instagram_post.key).toContain("instagram-post.png");
  });

  it("returns 400 when plain-content payload misses required content", async () => {
    const response = await worker.fetch(
      new Request("https://worker.test/generate-from-content", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: "Incomplete payload" })
      }),
      {} as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: string };
    expect(body.error).toContain("content");
  });
});

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
