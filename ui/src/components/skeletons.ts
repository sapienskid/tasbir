// Static skeleton HTML templates that use CSS variables from generated tokens

export function generateComponentsSkeleton(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Components Showcase</title>
  <style id="token-styles"></style>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: var(--font-sans);
      background: var(--surface-base);
      color: var(--text-primary);
      padding: var(--space-10);
      line-height: var(--leading-normal);
    }
    
    .container { max-width: 1200px; margin: 0 auto; }
    .section { margin-bottom: var(--space-12); }
    .section-title {
      font-size: var(--text-2xl);
      font-weight: var(--font-weight-bold);
      margin-bottom: var(--space-6);
      color: var(--text-primary);
    }
    
    /* Buttons */
    .button-group { display: flex; gap: var(--space-4); flex-wrap: wrap; }
    .btn {
      height: var(--button-height);
      padding: 0 var(--button-paddingX);
      border-radius: var(--button-radius);
      font-weight: var(--button-fontWeight);
      font-size: var(--button-fontSize);
      border: none;
      cursor: pointer;
      transition: all var(--duration-normal) var(--easing-default);
      font-family: var(--font-sans);
    }
    .btn-primary {
      background: var(--color-primary-500);
      color: var(--text-inverse);
    }
    .btn-primary:hover {
      background: var(--color-primary-600);
      transform: translateY(-1px);
      box-shadow: var(--shadow-md);
    }
    .btn-secondary {
      background: var(--color-secondary-500);
      color: var(--text-inverse);
    }
    .btn-outline {
      background: transparent;
      border: var(--border-normal) solid var(--color-primary-500);
      color: var(--color-primary-500);
    }
    
    /* Cards */
    .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-6); }
    .card {
      background: var(--surface-elevated);
      border-radius: var(--card-radius);
      padding: var(--card-padding);
      box-shadow: var(--shadow-sm);
      transition: all var(--duration-normal) var(--easing-default);
    }
    .card:hover {
      transform: translateY(-4px);
      box-shadow: var(--shadow-lg);
    }
    .card-title {
      font-size: var(--text-lg);
      font-weight: var(--font-weight-semibold);
      margin-bottom: var(--space-3);
      color: var(--text-primary);
    }
    .card-text {
      font-size: var(--text-base);
      color: var(--text-secondary);
      line-height: var(--leading-relaxed);
    }
    
    /* Badges */
    .badge-group { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; }
    .badge {
      height: var(--badge-height);
      padding: 0 var(--badge-paddingX);
      border-radius: var(--badge-radius);
      font-size: var(--badge-fontSize);
      font-weight: var(--badge-fontWeight);
      display: inline-flex;
      align-items: center;
      font-family: var(--font-sans);
    }
    .badge-primary { background: var(--color-primary-100); color: var(--color-primary-700); }
    .badge-success { background: var(--color-success); color: var(--text-inverse); opacity: 0.9; }
    .badge-warning { background: var(--color-warning); color: var(--text-inverse); opacity: 0.9; }
    .badge-error { background: var(--color-error); color: var(--text-inverse); opacity: 0.9; }
    
    /* Inputs */
    .form-group { margin-bottom: var(--space-5); max-width: 400px; }
    .label {
      display: block;
      font-size: var(--text-sm);
      font-weight: var(--font-weight-medium);
      margin-bottom: var(--space-2);
      color: var(--text-primary);
    }
    .input {
      width: 100%;
      height: var(--input-height);
      padding: 0 var(--input-paddingX);
      border: var(--input-borderWidth) solid var(--color-neutral-300);
      border-radius: var(--input-radius);
      font-size: var(--text-base);
      font-family: var(--font-sans);
      background: var(--surface-base);
      color: var(--text-primary);
      transition: all var(--duration-fast) var(--easing-default);
    }
    .input:focus {
      outline: none;
      border-color: var(--color-primary-500);
      box-shadow: 0 0 0 3px var(--color-primary-100);
    }
    
    /* Color Palette Preview */
    .color-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: var(--space-4); }
    .color-swatch {
      aspect-ratio: 1;
      border-radius: var(--radius-md);
      display: flex;
      align-items: flex-end;
      padding: var(--space-3);
      font-size: var(--text-xs);
      font-weight: var(--font-weight-semibold);
      font-family: var(--font-mono);
      box-shadow: var(--shadow-sm);
    }
    .swatch-primary { background: var(--color-primary-500); color: var(--text-inverse); }
    .swatch-secondary { background: var(--color-secondary-500); color: var(--text-inverse); }
    .swatch-accent { background: var(--color-accent-base); color: var(--text-inverse); }
    
    /* Shadow Showcase */
    .shadow-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-6); }
    .shadow-demo {
      background: var(--surface-elevated);
      border-radius: var(--radius-md);
      padding: var(--space-4);
      text-align: center;
      font-size: var(--text-sm);
      font-weight: var(--font-weight-medium);
      transition: transform var(--duration-normal) var(--easing-default);
      border: 1px solid var(--color-neutral-300);
    }
    .shadow-demo:hover { transform: scale(1.05); }
    .shadow-stages {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--space-2);
      margin-bottom: var(--space-2);
    }
    .shadow-stage {
      height: 82px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid rgba(148, 163, 184, 0.4);
      overflow: hidden;
    }
    .shadow-stage.light,
    .shadow-stage.dark {
      background: #ffffff;
    }
    .shadow-chip {
      width: 44px;
      height: 30px;
      border-radius: 6px;
      background: #334155;
    }
    .shadow-xs .shadow-chip { box-shadow: var(--shadow-xs); }
    .shadow-sm .shadow-chip { box-shadow: var(--shadow-sm); }
    .shadow-md .shadow-chip { box-shadow: var(--shadow-md); }
    .shadow-lg .shadow-chip { box-shadow: var(--shadow-lg); }
    .shadow-xl .shadow-chip { box-shadow: var(--shadow-xl); }
    .shadow-label {
      font-size: var(--text-xs);
      letter-spacing: var(--tracking-wider);
      color: var(--text-secondary);
      text-transform: uppercase;
    }
    
    /* Motion Showcase */
    @keyframes float {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-10px); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }
    .motion-demo {
      background: var(--color-primary-500);
      color: var(--text-inverse);
      padding: var(--space-4) var(--space-6);
      border-radius: var(--radius-md);
      font-weight: var(--font-weight-semibold);
      font-size: var(--text-sm);
      display: inline-block;
      margin: var(--space-2);
    }
    .motion-float { animation: float var(--duration-slower) var(--easing-default) infinite; }
    .motion-pulse { animation: pulse var(--duration-slow) var(--easing-default) infinite; }
    
    /* Type Scale Showcase */
    .type-scale { display: flex; flex-direction: column; gap: var(--space-6); }
    .type-scale-item { border-left: 3px solid var(--color-primary-500); padding-left: var(--space-4); }
    .type-scale-label {
      font-size: var(--text-xs);
      font-weight: var(--font-weight-medium);
      color: var(--text-muted);
      font-family: var(--font-mono);
      margin-bottom: var(--space-2);
      text-transform: uppercase;
      letter-spacing: var(--tracking-wide);
    }
    .type-scale-value {
      line-height: var(--leading-tight);
      color: var(--text-primary);
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="section">
      <h2 class="section-title">Color Palette</h2>
      <div class="color-grid">
        <div class="color-swatch swatch-primary">Primary</div>
        <div class="color-swatch swatch-secondary">Secondary</div>
        <div class="color-swatch swatch-accent">Accent</div>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Type Scale</h2>
      <div class="type-scale">
        <div class="type-scale-item">
          <div class="type-scale-label">text-7xl</div>
          <div class="type-scale-value" style="font-size: var(--text-7xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-6xl</div>
          <div class="type-scale-value" style="font-size: var(--text-6xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-5xl</div>
          <div class="type-scale-value" style="font-size: var(--text-5xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-4xl</div>
          <div class="type-scale-value" style="font-size: var(--text-4xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-3xl</div>
          <div class="type-scale-value" style="font-size: var(--text-3xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-2xl</div>
          <div class="type-scale-value" style="font-size: var(--text-2xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-xl</div>
          <div class="type-scale-value" style="font-size: var(--text-xl); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-lg</div>
          <div class="type-scale-value" style="font-size: var(--text-lg); font-weight: var(--font-weight-bold);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-base</div>
          <div class="type-scale-value" style="font-size: var(--text-base);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-sm</div>
          <div class="type-scale-value" style="font-size: var(--text-sm);">Aa</div>
        </div>
        <div class="type-scale-item">
          <div class="type-scale-label">text-xs</div>
          <div class="type-scale-value" style="font-size: var(--text-xs);">Aa</div>
        </div>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Buttons</h2>
      <div class="button-group">
        <button class="btn btn-primary">Primary Button</button>
        <button class="btn btn-secondary">Secondary Button</button>
        <button class="btn btn-outline">Outline Button</button>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Cards</h2>
      <div class="card-grid">
        <div class="card">
          <h3 class="card-title">Card Title</h3>
          <p class="card-text">This is a card component demonstrating the design system's typography, spacing, and elevation tokens in action.</p>
        </div>
        <div class="card">
          <h3 class="card-title">Another Card</h3>
          <p class="card-text">Cards use surface tokens for background, shadow tokens for depth, and spacing tokens for consistent padding.</p>
        </div>
        <div class="card">
          <h3 class="card-title">Third Card</h3>
          <p class="card-text">Hover over cards to see the motion timing and easing curves in effect.</p>
        </div>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Badges</h2>
      <div class="badge-group">
        <span class="badge badge-primary">Primary</span>
        <span class="badge badge-success">Success</span>
        <span class="badge badge-warning">Warning</span>
        <span class="badge badge-error">Error</span>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Form Inputs</h2>
      <div class="form-group">
        <label class="label">Email address</label>
        <input type="email" class="input" placeholder="you@example.com" />
      </div>
      <div class="form-group">
        <label class="label">Password</label>
        <input type="password" class="input" placeholder="••••••••" />
      </div>
    </div>
    
    <div class="section">
      <h2 class="section-title">Shadow System</h2>
      <div class="shadow-grid">
        <div class="shadow-demo shadow-xs">
          <div class="shadow-stages">
            <div class="shadow-stage light"><div class="shadow-chip"></div></div>
            <div class="shadow-stage dark"><div class="shadow-chip"></div></div>
          </div>
          <div class="shadow-label">XS</div>
        </div>
        <div class="shadow-demo shadow-sm">
          <div class="shadow-stages">
            <div class="shadow-stage light"><div class="shadow-chip"></div></div>
            <div class="shadow-stage dark"><div class="shadow-chip"></div></div>
          </div>
          <div class="shadow-label">SM</div>
        </div>
        <div class="shadow-demo shadow-md">
          <div class="shadow-stages">
            <div class="shadow-stage light"><div class="shadow-chip"></div></div>
            <div class="shadow-stage dark"><div class="shadow-chip"></div></div>
          </div>
          <div class="shadow-label">MD</div>
        </div>
        <div class="shadow-demo shadow-lg">
          <div class="shadow-stages">
            <div class="shadow-stage light"><div class="shadow-chip"></div></div>
            <div class="shadow-stage dark"><div class="shadow-chip"></div></div>
          </div>
          <div class="shadow-label">LG</div>
        </div>
        <div class="shadow-demo shadow-xl">
          <div class="shadow-stages">
            <div class="shadow-stage light"><div class="shadow-chip"></div></div>
            <div class="shadow-stage dark"><div class="shadow-chip"></div></div>
          </div>
          <div class="shadow-label">XL</div>
        </div>
      </div>
    </div>
    
    <div class="section">
      <h2 class="section-title">Motion Timing</h2>
      <div>
        <div class="motion-demo motion-float">Floating Animation</div>
        <div class="motion-demo motion-pulse">Pulse Animation</div>
      </div>
    </div>
  </div>
</body>
</html>`;
}

export function generateLandingPageSkeleton(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Landing Page</title>
  <style id="token-styles"></style>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: var(--font-sans);
      background: var(--surface-base);
      color: var(--text-primary);
      line-height: var(--leading-normal);
    }
    
    .hero {
      min-height: 80vh;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: var(--space-12);
      background: var(--gradient-hero);
      position: relative;
      overflow: hidden;
    }
    
    .hero::before {
      content: '';
      position: absolute;
      inset: 0;
      background: var(--surface-overlay);
      z-index: 1;
    }
    
    .hero-content {
      position: relative;
      z-index: 2;
      max-width: 900px;
    }
    
    .hero-title {
      font-size: var(--text-6xl);
      font-weight: var(--font-weight-black);
      margin-bottom: var(--space-6);
      color: var(--text-inverse);
      letter-spacing: var(--tracking-tight);
      line-height: var(--leading-tight);
    }
    
    .hero-subtitle {
      font-size: var(--text-xl);
      color: var(--text-inverse);
      margin-bottom: var(--space-8);
      opacity: 0.95;
      line-height: var(--leading-relaxed);
    }
    
    .cta-group {
      display: flex;
      gap: var(--space-4);
      justify-content: center;
      flex-wrap: wrap;
    }
    
    .btn {
      height: var(--button-heightLg);
      padding: 0 var(--space-8);
      border-radius: var(--button-radius);
      font-weight: var(--button-fontWeight);
      font-size: var(--text-lg);
      border: none;
      cursor: pointer;
      transition: all var(--duration-normal) var(--easing-default);
      font-family: var(--font-sans);
    }
    
    .btn-primary {
      background: var(--text-inverse);
      color: var(--color-primary-600);
    }
    
    .btn-primary:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-xl);
    }
    
    .btn-outline {
      background: transparent;
      border: 2px solid var(--text-inverse);
      color: var(--text-inverse);
    }
    
    .btn-outline:hover {
      background: var(--text-inverse);
      color: var(--color-primary-600);
    }
    
    .features {
      padding: var(--space-14) var(--space-8);
      max-width: 1200px;
      margin: 0 auto;
    }
    
    .features-title {
      font-size: var(--text-4xl);
      font-weight: var(--font-weight-bold);
      text-align: center;
      margin-bottom: var(--space-10);
      color: var(--text-primary);
    }
    
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: var(--space-8);
    }
    
    .feature-card {
      padding: var(--space-8);
      background: var(--surface-elevated);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow-md);
      transition: all var(--duration-normal) var(--easing-default);
    }
    
    .feature-card:hover {
      transform: translateY(-4px);
      box-shadow: var(--shadow-xl);
    }
    
    .feature-icon {
      width: 48px;
      height: 48px;
      background: var(--color-primary-500);
      border-radius: var(--radius-lg);
      margin-bottom: var(--space-5);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: var(--text-2xl);
    }
    
    .feature-title {
      font-size: var(--text-xl);
      font-weight: var(--font-weight-semibold);
      margin-bottom: var(--space-3);
      color: var(--text-primary);
    }
    
    .feature-text {
      font-size: var(--text-base);
      color: var(--text-secondary);
      line-height: var(--leading-relaxed);
    }
  </style>
</head>
<body>
  <section class="hero">
    <div class="hero-content">
      <h1 class="hero-title">Beautiful Design Systems Made Simple</h1>
      <p class="hero-subtitle">Generate complete, production-ready design tokens powered by AI and proper design principles</p>
      <div class="cta-group">
        <button class="btn btn-primary">Get Started</button>
        <button class="btn btn-outline">Learn More</button>
      </div>
    </div>
  </section>
  
  <section class="features">
    <h2 class="features-title">Why Choose Us</h2>
    <div class="feature-grid">
      <div class="feature-card">
        <div class="feature-icon">🎨</div>
        <h3 class="feature-title">Color Theory</h3>
        <p class="feature-text">Harmonious color palettes generated using proper color theory and WCAG contrast ratios.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">✨</div>
        <h3 class="feature-title">Typography</h3>
        <p class="feature-text">Carefully paired fonts with mathematical type scales and proper spacing.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">⚡</div>
        <h3 class="feature-title">Instant Preview</h3>
        <p class="feature-text">See your design system come to life instantly with live component previews.</p>
      </div>
    </div>
  </section>
</body>
</html>`;
}

export function generatePosterSkeleton(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Poster</title>
  <style id="token-styles"></style>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: var(--font-sans);
      background: var(--gradient-hero);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: var(--space-8);
    }
    
    .poster {
      width: 100%;
      max-width: 800px;
      aspect-ratio: 3/4;
      background: var(--surface-elevated);
      border-radius: var(--radius-2xl);
      padding: var(--space-12);
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      text-align: center;
      box-shadow: var(--shadow-xl);
      position: relative;
      overflow: hidden;
    }
    
    .poster::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40%;
      background: var(--gradient-primary);
      opacity: 0.1;
      z-index: 0;
    }
    
    .poster-content {
      position: relative;
      z-index: 1;
    }
    
    .poster-label {
      font-size: var(--text-sm);
      text-transform: uppercase;
      letter-spacing: var(--tracking-widest);
      font-weight: var(--font-weight-bold);
      color: var(--color-primary-500);
      margin-bottom: var(--space-4);
    }
    
    .poster-title {
      font-size: var(--text-7xl);
      font-weight: var(--font-weight-black);
      line-height: var(--leading-tight);
      letter-spacing: var(--tracking-tight);
      margin-bottom: var(--space-6);
      background: var(--gradient-primary);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    .poster-subtitle {
      font-size: var(--text-2xl);
      font-family: var(--font-serif);
      color: var(--text-secondary);
      margin-bottom: var(--space-8);
      line-height: var(--leading-relaxed);
      max-width: 600px;
    }
    
    .poster-footer {
      margin-top: var(--space-10);
      display: flex;
      gap: var(--space-6);
      align-items: center;
    }
    
    .badge {
      height: var(--badge-height);
      padding: 0 var(--badge-paddingX);
      border-radius: var(--badge-radius);
      font-size: var(--badge-fontSize);
      font-weight: var(--badge-fontWeight);
      background: var(--color-accent-base);
      color: var(--text-inverse);
      display: inline-flex;
      align-items: center;
    }
    
    .divider {
      width: 60px;
      height: 2px;
      background: var(--color-primary-500);
    }
  </style>
</head>
<body>
  <div class="poster">
    <div class="poster-content">
      <div class="poster-label">Design System</div>
      <h1 class="poster-title">Tasbir</h1>
      <p class="poster-subtitle">Beautiful, accessible, and production-ready design tokens crafted with precision</p>
      <div class="poster-footer">
        <span class="badge">Color Theory</span>
        <div class="divider"></div>
        <span class="badge">Typography</span>
        <div class="divider"></div>
        <span class="badge">Spacing</span>
      </div>
    </div>
  </div>
</body>
</html>`;
}
