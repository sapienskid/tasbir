# Generation quality improvements

The operator authorized all seven generation improvements: coherent carousel
narratives, stronger hook selection, copy-aware layouts, explanatory media,
actionable verifier corrections, curated brand references, and whole-carousel
review. This extends the existing agents and free-tier Gateway transport.

## Data flow

Planner emits a typed narrative beat for every requested slide. User platform,
ratio and slide-count pins remain authoritative. Pinned structure still needs
no planner call. Copywriter develops the concrete narrative and three distinct
hook candidates within its existing response. Candidates carry a source passage
and bounded specificity/relevance/faithfulness judgments. Selection rejects
unsupported figures, unsupported source passages and generic hype. The selected
hook becomes the actual carousel cover. Explicit copy overrides and verbatim
content remain authoritative.

Before layout, readable body budgets distinguish landscape, square/portrait and
story formats. Over-budget generated copy gets one bounded revision attempt.
Template selection requires slots for nonempty editorial fields and ranks
content density/composition; the designer receives the same profile. Neither
path may use smaller type to hide a copy-fit problem. Human template pins win.

Media planning records what an image explains and can deliberately choose none.
None suppresses fallback photos and illustrations. Only planned illustrations
and charts render; a missing photo never acquires unrelated procedural art.
User-supplied images remain pinned. Media relevance failures can remove generated
media without another search round.

Verifier corrections are typed as copy, layout or media with an element,
problem, concrete action and priority. Legacy and deterministic failures get
compatible routable corrections. Copy corrections return to copywriting;
geometry goes to design; irrelevant generated media can be removed. Every
retry actually rebuilds failed HTML. High-priority copy/media failures cannot
be overridden solely by a high visual score. Revision attempts remain bounded
by the existing verifier retry setting.

## Explicit learning

The Quality inspector offers approve/reject feedback. Saving a future reference
requires a separate opt-in and an explanatory note. Ordinary edits, approval
alone, and model scores never create references. References snapshot edited
structured copy, brand/category, composition and template identity. They live
in private `generation.example.*` app_settings records, survive task retention,
and use existing configuration export/import without a new backup format.
The list is removable from Studio; rejection revokes a reference for that frame.

Retrieval takes at most three references from the same brand and category.
Copywriter receives bounded copy/rationale only. Designer receives composition
and rationale, never previous token values or HTML. Approved template identities
are soft preferences below content fit. Prior claims must not become facts in
a new post.

## Set review and publication

After duplicate-media correction, each carousel gets deterministic repetition
checks and one bounded typed text review of flow, distinctness, terminology and
whether the ending delivers the hook. `generation.sequence_review` is a typed,
Studio-editable switch. Existing opt-in vision review additionally judges visual
rhythm and readable density. Verbatim text is exempt from semantic rewriting.
Model unavailability preserves deterministic checks and is logged; it is not
treated as a successful semantic judgment.

Publication runs after the final sequence review. Failed sets hold every slide
of that carousel without blocking unrelated single posts. Copy QA applies to
carousel slides through their base platform, and failed visual verification
also holds publication. A resumed run replaces its prior sequence judgment.

## Validation

Regression tests cover pins, hook grounding and cover application, density and
missing slots, no-media behavior, actual design retries, routed copy/media
corrections, carousel-scoped holds, explicit curation, edited-copy snapshots,
brand/category isolation, authentication, rejection/deletion, retention survival
and backup round-trips. Frontend tests cover opt-in behavior and required notes.
The production frontend build and complete backend suite remain release checks.
Automated tests verify these contracts; measuring aesthetic gains still needs
human review of representative live generations.
