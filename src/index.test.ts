import { beforeEach, describe, expect, it, vi } from "vitest";

const launchMock = vi.fn();
const TEST_API_KEY = "test-key";
const TEST_WEBHOOK_SECRET = "ghost-webhook-secret";
const TEST_WEBHOOK_TOKEN = "ghost-webhook-token";

vi.mock("@cloudflare/puppeteer", () => ({
  default: {
    launch: launchMock
  }
}));

vi.mock("agents", () => ({
  Agent: class {}
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

  it("allows preview requests without API key when preview auth is disabled by env override", async () => {
    const response = await worker.fetch(
      new Request("https://worker.test/template/instagram-portrait?title=Hello&caption=World"),
      { API_KEYS: TEST_API_KEY, API_AUTH_REQUIRE_FOR_PREVIEW: "false" } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
  });

  it("renders template endpoint without CDN script and with token variables", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template/instagram-portrait?title=Hello&caption=World"),
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

  it("renders markdown and math syntax into rich html wrappers", async () => {
    const response = await worker.fetch(
      authorizedRequest(
        "https://worker.test/template/instagram-portrait?templateId=layout/editorial" +
          "&title=%2A%2ABold%2A%2A%20headline" +
          "&caption=Inline%20math%20%24a%5E2%2Bb%5E2%3Dc%5E2%24%0A%0A-%20item%20one%0A-%20item%20two"
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain('<span class="rich-text rich-text-inline"><strong>Bold</strong> headline</span>');
    expect(html).toContain('class="rich-text rich-text-block"');
    expect(html).toContain('class="rich-math rich-math-inline"');
    expect(html).toContain("<ul>");
  });

  it("renders mermaid fences into deferred diagram placeholders", async () => {
    const diagramMarkdown = encodeURIComponent("```mermaid\ngraph TD\nA-->B\n```");
    const response = await worker.fetch(
      authorizedRequest(
        `https://worker.test/template/carousel-post?templateId=layout/carousel-header&title=Flow&heading=Flow&body=${diagramMarkdown}&slide=1&total=3`
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain('class="rich-mermaid rich-mermaid-block"');
    expect(html).toContain("data-mermaid=");
    expect(html).toContain("__RICH_RENDER_DONE__");
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

  it("returns 404 for removed preview gallery endpoint", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/preview/gallery"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(404);
  });

  it("resolves preview templates with slot values", async () => {
    const response = await worker.fetch(
      authorizedRequest(
        "https://worker.test/template/carousel-post?templateId=layout/carousel-header&slot.series_label=Read+More&heading=Growth&body=Issue+01&slide=1&total=5"
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain('data-template-id="layout/carousel-header"');
    expect(html).not.toContain("data-template-archetype=");
    expect(html).toContain("Read More");
  });

  it("renders deterministic illustration element tokens when slot.illustration_seed is set", async () => {
    const baseUrl =
      "https://worker.test/template/instagram-portrait?templateId=layout/editorial";
    const responseA1 = await worker.fetch(
      authorizedRequest(`${baseUrl}&slot.illustration_seed=seed-alpha`),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );
    const responseA2 = await worker.fetch(
      authorizedRequest(`${baseUrl}&slot.illustration_seed=seed-alpha`),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );
    const responseB = await worker.fetch(
      authorizedRequest(`${baseUrl}&slot.illustration_seed=seed-beta`),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(responseA1.status).toBe(200);
    expect(responseA2.status).toBe(200);
    expect(responseB.status).toBe(200);

    const htmlA1 = await responseA1.text();
    const htmlA2 = await responseA2.text();
    const htmlB = await responseB.text();
    const illustrationA1 = extractIllustrationSignature(htmlA1);
    const illustrationA2 = extractIllustrationSignature(htmlA2);
    const illustrationB = extractIllustrationSignature(htmlB);
    const markerClassA1 = extractIllustrationMarkerClass(htmlA1);

    expect(illustrationA1.length).toBeGreaterThan(0);
    expect(illustrationA1).toBe(illustrationA2);
    expect(illustrationA1).not.toBe(illustrationB);
    expect(markerClassA1).not.toContain("hidden");
  });

  it("auto-seeds illustration when no seed is provided in preview", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template/instagram-portrait?templateId=layout/editorial"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    const markerClass = extractIllustrationMarkerClass(html);
    const illustration = extractIllustrationSignature(html);

    expect(markerClass).not.toContain("hidden");
    expect(html).toContain('data-illustration-mark="1"');
    expect(illustration.length).toBeGreaterThan(0);
  });

  it("supports black-white foreground/background swap in preview", async () => {
    const response = await worker.fetch(
      authorizedRequest(
        "https://worker.test/template/twitter-card?templateId=layout/with-media-split&title=Signal&caption=Keep+it+simple&colorSwap=swap"
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain('data-color-swap="swap"');
    expect(html).toMatch(/object-contain[^"]*invert/i);
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
        "https://worker.test/template/twitter-card?templateId=layout/with-media-split&title=Data+Story&caption=Signal+beats+noise"
      ),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).not.toContain("style-data");
  });

  it("returns 404 for removed template catalog endpoint", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/template-catalog"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(404);
  });

  it("returns 404 for removed preview workspace endpoint", async () => {
    const response = await worker.fetch(
      authorizedRequest("https://worker.test/preview"),
      { API_KEYS: TEST_API_KEY } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(404);
  });

  it("accepts Ghost-signed webhook requests", async () => {
    launchMock.mockResolvedValue(fakeBrowser());
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          posts: [
            {
              id: "post-1",
              title: "Webhook Triggered Post",
              slug: "webhook-triggered-post",
              url: "https://blog.example.com/webhook-triggered-post/",
              plaintext: "Webhook content body",
              excerpt: "Webhook excerpt"
            }
          ]
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" }
        }
      )
    );

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "Webhook caption for instagram.",
            twitter_caption: "Webhook caption for twitter.",
            linkedin_caption: "Webhook caption for linkedin.",
            carousel_slides: [
              { heading: "One", body: "First body." },
              { heading: "Two", body: "Second body." },
              { heading: "Three", body: "Third body." },
              { heading: "Four", body: "Fourth body." },
              { heading: "Five", body: "Fifth body." }
            ],
            hashtags: ["#workflow", "#ghost", "#webhook", "#content", "#automation"],
            image_prompt: "Minimal editorial visual",
            use_feature_image: false,
            slot_content: {
              headline: "Webhook headline"
            }
          })
        }))
      },
      BROWSER: {},
      OUTPUT_BUCKET: {
        put: vi.fn(async () => null)
      },
      GHOST_API_URL: "https://blog.example.com/ghost/api/content",
      GHOST_CONTENT_API_KEY: "content-api-key",
      GHOST_WEBHOOK_SECRET: TEST_WEBHOOK_SECRET,
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const payload = {
      post: {
        current: {
          slug: "webhook-triggered-post"
        }
      }
    };
    const rawPayload = JSON.stringify(payload);
    const timestamp = String(Date.now());
    const signature = await computeHmacSha256Hex(TEST_WEBHOOK_SECRET, `${rawPayload}${timestamp}`);

    const response = await worker.fetch(
      new Request("https://worker.test/webhook/ghost", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-ghost-signature": `sha256=${signature}, t=${timestamp}`
        },
        body: rawPayload
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as { ok: boolean; slug: string };
    expect(body.ok).toBe(true);
    expect(body.slug).toBe("webhook-triggered-post");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0]?.[0])).toContain("/posts/slug/webhook-triggered-post/");
    fetchSpy.mockRestore();
  });

  it("accepts legacy x-webhook-token requests", async () => {
    launchMock.mockResolvedValue(fakeBrowser());
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          posts: [
            {
              id: "post-2",
              title: "Legacy Token Webhook Post",
              slug: "legacy-token-post",
              url: "https://blog.example.com/legacy-token-post/",
              plaintext: "Webhook content body",
              excerpt: "Webhook excerpt"
            }
          ]
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" }
        }
      )
    );

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "Webhook caption for instagram.",
            twitter_caption: "Webhook caption for twitter.",
            linkedin_caption: "Webhook caption for linkedin.",
            carousel_slides: [
              { heading: "One", body: "First body." },
              { heading: "Two", body: "Second body." },
              { heading: "Three", body: "Third body." },
              { heading: "Four", body: "Fourth body." },
              { heading: "Five", body: "Fifth body." }
            ],
            hashtags: ["#workflow", "#ghost", "#webhook", "#content", "#automation"],
            image_prompt: "Minimal editorial visual",
            use_feature_image: false,
            slot_content: {
              headline: "Webhook headline"
            }
          })
        }))
      },
      BROWSER: {},
      OUTPUT_BUCKET: {
        put: vi.fn(async () => null)
      },
      GHOST_API_URL: "https://blog.example.com/ghost/api/content",
      GHOST_CONTENT_API_KEY: "content-api-key",
      GHOST_WEBHOOK_TOKEN: TEST_WEBHOOK_TOKEN,
      R2_KEY_PREFIX: "social-assets"
    } as never;

    const response = await worker.fetch(
      new Request("https://worker.test/webhook/ghost", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-webhook-token": TEST_WEBHOOK_TOKEN
        },
        body: JSON.stringify({
          post: {
            current: {
              slug: "legacy-token-post"
            }
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as { ok: boolean; slug: string };
    expect(body.ok).toBe(true);
    expect(body.slug).toBe("legacy-token-post");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0]?.[0])).toContain("/posts/slug/legacy-token-post/");
    fetchSpy.mockRestore();
  });

  it("rejects Ghost webhook when signature is invalid", async () => {
    const response = await worker.fetch(
      new Request("https://worker.test/webhook/ghost", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-ghost-signature": "sha256=deadbeef, t=1234567890123"
        },
        body: JSON.stringify({
          post: {
            current: {
              slug: "invalid-signature-post"
            }
          }
        })
      }),
      { GHOST_WEBHOOK_SECRET: TEST_WEBHOOK_SECRET } as never,
      fakeExecutionContext()
    );

    expect(response.status).toBe(401);
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

  it("returns campaign_plan and campaign_outputs with per-platform deterministic posts", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "Structured platform copy for campaign output.",
            twitter_caption: "Short native post with clear payoff.",
            linkedin_caption: "Professional post with problem-insight-action.",
            carousel_slides: [
              { heading: "Step 1", body: "Extract the campaign signal from source content." },
              { heading: "Step 2", body: "Map it into deterministic template slots." },
              { heading: "Step 3", body: "Render each platform as a distinct asset." },
              { heading: "Step 4", body: "Review outputs and publish with confidence." },
              { heading: "Step 5", body: "Track performance and refine the next cycle." }
            ],
            hashtags: ["#contentops", "#social", "#campaign", "#automation", "#workflow"],
            image_prompt: "unused in deterministic campaign mode",
            stock_search_query: "unused",
            use_feature_image: false,
            slot_content: {
              headline: "Distinct platform outputs",
              supporting_line: "No cross-platform resize reuse",
              cta_text: "Read more"
            }
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
          title: "Campaign Planner Test",
          content: "One source, multiple platform-native campaign posts.",
          image: {
            mode: "none"
          },
          campaign: {
            platforms: ["instagram-square", "twitter-card"],
            counts: {
              "instagram-square": 2,
              "twitter-card": 1
            }
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      requested_formats: string[];
      campaign_plan: {
        strategy: string;
        platforms: Array<{ platform: string; count: number; posts: Array<{ index: number; template_id: string; angle_preset: string }> }>;
      };
      campaign_outputs: Array<{ platform: string; index: number; assets: Array<{ key: string }> }>;
      assets: {
        instagram_square: { key: string } | null;
        twitter_card: { key: string } | null;
      };
    };

    expect(body.requested_formats).toEqual(["instagram-square", "twitter-card"]);
    expect(body.campaign_plan.strategy).toBe("template-rotation-angle-presets");
    expect(body.campaign_plan.platforms).toHaveLength(2);
    expect(body.campaign_plan.platforms.find((item) => item.platform === "instagram-square")?.count).toBe(2);
    expect(body.campaign_plan.platforms.find((item) => item.platform === "twitter-card")?.count).toBe(1);
    expect(body.campaign_outputs).toHaveLength(3);

    const assetKeys = body.campaign_outputs.flatMap((output) => output.assets.map((asset) => asset.key));
    expect(new Set(assetKeys).size).toBe(assetKeys.length);
    expect(assetKeys.some((key) => /\/campaign-[^/]+-p\d+\//.test(key))).toBe(false);
    expect(body.assets.instagram_square?.key).toContain("instagram-square.png");
    expect(body.assets.twitter_card?.key).toContain("twitter-card.png");
  });

  it("rejects stock image mode in campaign mode", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const env = {
      AI: {
        run: vi.fn(async () => ({
          response: JSON.stringify({
            instagram_caption: "test",
            twitter_caption: "test",
            linkedin_caption: "test",
            carousel_slides: [
              { heading: "A", body: "B." },
              { heading: "C", body: "D." },
              { heading: "E", body: "F." },
              { heading: "G", body: "H." },
              { heading: "I", body: "J." }
            ],
            hashtags: ["#a", "#b", "#c", "#d", "#e"],
            image_prompt: "test",
            stock_search_query: "test",
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
          title: "Campaign Invalid Image Mode",
          content: "campaign body",
          campaign: {
            platforms: ["twitter-card"],
            counts: {
              "twitter-card": 1
            }
          },
          image: {
            mode: "stock"
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: string };
    expect(body.error).toContain("image.mode");
  });

  it("supports ai image mode in campaign mode", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const aiRun = vi
      .fn()
      .mockImplementationOnce(async () => ({
        response: JSON.stringify({
          instagram_caption: "test",
          twitter_caption: "test",
          linkedin_caption: "test",
          carousel_slides: [
            { heading: "A", body: "B." },
            { heading: "C", body: "D." },
            { heading: "E", body: "F." },
            { heading: "G", body: "H." },
            { heading: "I", body: "J." }
          ],
          hashtags: ["#a", "#b", "#c", "#d", "#e"],
          image_prompt: "cinematic editorial illustration",
          stock_search_query: "unused",
          use_feature_image: false,
          slot_content: {}
        })
      }))
      .mockImplementationOnce(async () => new Uint8Array([1, 2, 3, 4]));

    const env = {
      AI: {
        run: aiRun
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
          title: "Campaign AI Image Mode",
          content: "campaign body",
          campaign: {
            platforms: ["twitter-card"],
            counts: {
              "twitter-card": 1
            }
          },
          image: {
            mode: "ai"
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      image_source: { source: string };
      campaign_outputs: Array<{ image_source: { source: string } }>;
    };
    expect(body.image_source.source).toBe("ai");
    expect(body.campaign_outputs[0]?.image_source.source).toBe("ai");
  });

  it("keeps planner candidate context even when prompt is provided", async () => {
    launchMock.mockResolvedValue(fakeBrowser());
    let plannerPrompt = "";
    const aiRun = vi
      .fn()
      .mockImplementationOnce(async (_model: unknown, payload: { messages?: Array<{ content?: string }> }) => {
        plannerPrompt = payload.messages?.[1]?.content ?? "";
        return {
          response: JSON.stringify({
            template_ids: {
              "twitter-card": "layout/statement-cta"
            }
          })
        };
      })
      .mockImplementation(async () => ({
        response: JSON.stringify({
          instagram_caption: "Campaign copy for instagram.",
          twitter_caption: "Campaign copy for twitter.",
          linkedin_caption: "Campaign copy for linkedin.",
          carousel_slides: [
            { heading: "One", body: "First supporting point." },
            { heading: "Two", body: "Second supporting point." },
            { heading: "Three", body: "Third supporting point." },
            { heading: "Four", body: "Fourth supporting point." },
            { heading: "Five", body: "Fifth supporting point." }
          ],
          hashtags: ["#contentops", "#social", "#workflow", "#growth", "#automation"],
          image_prompt: "A minimal deterministic scene",
          stock_search_query: "content workflow",
          use_feature_image: false,
          slot_content: {
            headline: "Prompt test headline"
          }
        })
      }));

    const env = {
      AI: {
        run: aiRun
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
          title: "Planner Prompt Coverage",
          content: "Ensure candidate templates are present in planner context.",
          prompt: "Use an assertive, technical tone.",
          output: {
            formats: ["twitter-card"]
          },
          image: {
            mode: "none"
          }
        })
      }),
      env,
      fakeExecutionContext()
    );

    expect(response.status).toBe(200);
    expect(plannerPrompt).toContain("Requested formats and candidate templates:");
    expect(plannerPrompt).toContain("format: twitter-card");
    expect(plannerPrompt).toContain("<user_brief>");
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

  it("handles lorem ipsum heading and paragraph size variants", async () => {
    launchMock.mockResolvedValue(fakeBrowser());

    const variants = [
      {
        id: "short",
        headingWords: 4,
        paragraphSentences: 1,
        wordsPerSentence: 12
      },
      {
        id: "medium",
        headingWords: 8,
        paragraphSentences: 2,
        wordsPerSentence: 18
      },
      {
        id: "long",
        headingWords: 16,
        paragraphSentences: 4,
        wordsPerSentence: 28
      }
    ];

    for (const [index, variant] of variants.entries()) {
      const headingText = loremSentence(variant.headingWords, index * 17).replace(/\.$/, "");
      const paragraphText = loremParagraph(variant.paragraphSentences, variant.wordsPerSentence, index * 23);

      const env = {
        AI: {
          run: vi.fn(async () => ({
            response: JSON.stringify({
              instagram_caption: paragraphText,
              twitter_caption: paragraphText,
              linkedin_caption: paragraphText,
              carousel_slides: [
                { heading: headingText, body: paragraphText },
                { heading: headingText, body: paragraphText },
                { heading: headingText, body: paragraphText },
                { heading: headingText, body: paragraphText },
                { heading: headingText, body: paragraphText }
              ],
              hashtags: ["#workflow", "#contentops", "#socialmedia", "#automation", "#cloudflare"],
              image_prompt: "A neutral editorial gradient background with clean negative space",
              stock_search_query: "lorem stress",
              use_feature_image: false,
              slot_content: {
                headline: headingText,
                body: paragraphText
              }
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
            title: `Lorem Variant ${variant.id}`,
            content: paragraphText,
            output: {
              formats: ["carousel-post"],
              carouselSlides: 5
            },
            image: {
              mode: "none"
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

      expect(body.llm_output.carousel_slides).toHaveLength(5);
      expect(body.llm_output.instagram_caption.length).toBeLessThanOrEqual(600);
      expect(body.llm_output.twitter_caption.length).toBeLessThanOrEqual(280);
      expect(body.llm_output.linkedin_caption.length).toBeLessThanOrEqual(900);

      for (const slide of body.llm_output.carousel_slides) {
        expect(slide.heading.length).toBeGreaterThan(0);
        expect(slide.heading.length).toBeLessThanOrEqual(72);
        expect(slide.body.length).toBeGreaterThan(0);
        expect(slide.body.length).toBeLessThanOrEqual(260);
      }
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
    waitForFunction: vi.fn(async () => undefined),
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

async function computeHmacSha256Hex(secret: string, payload: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return Array.from(new Uint8Array(signature))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function extractIllustrationSignature(html: string): string {
  const classSignature = extractIllustrationMarkerClass(html);
  const svgSignature = extractIllustrationMarkerSvg(html);
  return `${classSignature}|${svgSignature}`;
}

function extractIllustrationMarkerClass(html: string): string {
  const match = html.match(
    /<span\s+aria-hidden="true"\s+data-illustration-mark="1"\s+class="([^"]+)"/i
  );
  return (match?.[1] ?? "").replace(/\s+/g, " ").trim();
}

function extractIllustrationMarkerSvg(html: string): string {
  const match = html.match(
    /<span\s+aria-hidden="true"\s+data-illustration-mark="1"\s+class="[^"]*">([\s\S]*?)<\/span>/i
  );
  return (match?.[1] ?? "").replace(/\s+/g, " ").trim();
}

function loremWords(wordCount: number, seed = 0): string {
  const words = [
    "lorem",
    "ipsum",
    "dolor",
    "sit",
    "amet",
    "consectetur",
    "adipiscing",
    "elit",
    "sed",
    "do",
    "eiusmod",
    "tempor",
    "incididunt",
    "ut",
    "labore",
    "et",
    "dolore",
    "magna",
    "aliqua",
    "enim",
    "minim",
    "veniam",
    "quis",
    "nostrud",
    "exercitation",
    "ullamco",
    "laboris",
    "nisi",
    "aliquip",
    "commodo",
    "consequat"
  ];
  const count = Math.max(1, Math.floor(wordCount));
  const output: string[] = [];
  for (let index = 0; index < count; index += 1) {
    output.push(words[(seed + index) % words.length]);
  }
  return output.join(" ");
}

function loremSentence(wordCount: number, seed = 0): string {
  const base = loremWords(wordCount, seed);
  return `${base.slice(0, 1).toUpperCase()}${base.slice(1)}.`;
}

function loremParagraph(sentenceCount: number, wordsPerSentence: number, seed = 0): string {
  const sentences: string[] = [];
  for (let index = 0; index < sentenceCount; index += 1) {
    sentences.push(loremSentence(wordsPerSentence, seed + index * 7));
  }
  return sentences.join(" ");
}
