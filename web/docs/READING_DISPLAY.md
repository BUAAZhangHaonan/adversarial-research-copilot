# Existing research records: reading display

Collection and completed result pages use a separate reading view. The collection keeps the returned record order and exposes all/discover/develop/debate filters. Discovery results lead with the existing whole-run overview when explicitly available, then a card index and the card wall. Without such an overview, the page displays counts and a verbatim first sentence of each card's value; it does not synthesize a research conclusion.

The main card keeps the scene, research question, proposed idea, comparison, implementation basis and value. Existing presentation text is reused when available; legacy records use their original fields. Technical sections and references are disclosures. Negative decision reasons remain visible, all original fields and evidence limits remain available, and every source file is accessible. Link labels and percentages are preserved; only external URLs move out of the primary prose. This is display organization, not a new model result or scientific revision.

Develop and debate pages open the latest explicitly numbered nontechnical document and retain every earlier document version. Taking a selected card to judgment carries its actual card ID and version. Relative document links open only files listed in that same record. Pending, interrupted and other incomplete runs retain the existing progress and recovery view.

CurrentRun continues to honor explicit selection metadata. If an older server returns HTTP 404 for the visibility capability, it verifies access using the ordinary run/job endpoint. HTTP 401, 403, 410 and server failures never activate this fallback. No authentication or registry change is required to deploy these static resources to the older server.

## Validation

From `client`, run `./node_modules/.bin/tsc --noEmit --incremental false`, `node scripts/reading-content.mjs`, and `./node_modules/.bin/vite build`. The content check uses Vite's installed esbuild. The browser script additionally requires an already installed `playwright` package and Chrome, matching the existing regression environment; it never installs dependencies automatically.

Run `READING_DIST=/absolute/path/to/test-dist READING_WORK_DIR=/absolute/ignored/output node scripts/reading-regression.mjs`. Optionally set `READING_BEFORE_DIST` to an old static build for comparison screenshots. `READING_TEST_FILTER` runs a selected scenario and writes a separate targeted result. All APIs are mocked; these scripts never authenticate to production, read private research records, submit real jobs, or call a model.

The synthetic fixture contains seven records (five discover, one develop, one debate) and 21 idea cards. It covers stage filters, summary/card reading, references, full negative evidence, original files and relative links, handoffs and document versions, back/refresh, 375px layout, late response isolation, visibility compatibility, permission/error blocking, explicitly selected version changes, and flip/reset controls. Screenshots identify themselves as synthetic acceptance evidence. Actual private records require separate acceptance in the user's existing authenticated browser.

## Static release

Back up the entire existing `client/dist` before release. Copy new immutable assets additively and replace `index.html` atomically last. Keep old assets for existing browser tabs. Verify served index and asset hashes, HTTP 200 for the homepage/assets and unchanged HTTP 401 for unauthenticated protected endpoints. The existing server process need not restart. Preserve the backup and release manifest; rollback restores the previous index atomically. Research data, source files, authentication configuration and model-result versions are outside this release.
