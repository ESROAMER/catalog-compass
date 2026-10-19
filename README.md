# Catalog Compass

A small local workbench for reviewing supplier product CSVs before import.

A local open-weight model, or a model from your chosen API service, suggests what unfamiliar columns mean. You confirm the mapping. Deterministic checks then identify missing prices, duplicate SKUs and conflicting records, with row-level evidence. The original file is never edited.

[Watch the 2-minute 25-second demo (MP4)](submission/video/catalog-compass-demo.mp4) · [Read the English article draft](submission/article.en.md) · [Try the fictional supplier CSV](submission/demo-supplier.csv)

Built from scratch on October 15, 2026 for the Hacktoberfest Open-Source AI Challenge, Week 2: Side Hustle. This is an initial prototype, not a submitted contest entry.

## Run locally

Requirements: Python 3.11+ and a modern browser. The web application uses only Python's standard library and plain HTML/CSS/JavaScript. No pip or npm installation is needed.

```powershell
python app.py --open
```

On Windows, you can instead double-click **Start Catalog Compass.cmd**. Open `http://127.0.0.1:8765` if the browser does not open automatically. You can load a sample, manually select columns and run checks immediately.

Select **AI settings** at the top of the page, then choose one of two options:

- **API service:** no local model download. Choose a provider preset or enter an OpenAI-compatible Chat Completions base URL, model ID and API key. Review the destination, tick the sample-sharing checkbox, and select **Test & use API**. The connection test sends a short fixed prompt, never your uploaded catalog, and may incur a small API charge. It verifies connectivity and JSON output, not mapping accuracy. Close settings, load a CSV, then select **Suggest with AI**.
- **Local model:** select **Set up & start local AI (~672 MB)** on first use, or **Start local AI** after installation. Wait for the ready message, then select **Use local model**. If GPU startup fails, tick **Use CPU mode** and retry. The one-click installer supports Windows x64; keep the app running during installation.

The API presets use the documented [DeepSeek base URL and model](https://api-docs.deepseek.com/) and [OpenRouter base URL](https://openrouter.ai/docs/api/reference/overview). OpenRouter requires you to enter an available model ID. Model availability and charges depend on the provider. The default output setting is JSON object; **Advanced** offers strict JSON schema or prompt-only output for compatible providers. This is a Chat Completions adapter, not support for every provider-specific API. If the provider rejects JSON mode, try prompt-only output; returned mappings still undergo the same validation.

API keys stay in memory for the current page and request. The app does not write them to browser storage or disk. **Clear API settings** or reloading the page removes the key. Only column headers and up to three sample values per column (each capped at 100 characters) are sent for suggestions. The full CSV remains in the local application; the provider receives those samples and applies its own data policies. Remote API URLs must use HTTPS. HTTP is accepted only for loopback testing. No API account or credits are included.

The equivalent manual local-model setup is:

```powershell
python scripts/setup_model.py
powershell -ExecutionPolicy Bypass -File scripts/start_model.ps1
python app.py
```

Setup downloads a pinned llama.cpp Windows runtime and Qwen3-0.6B-GGUF into `.runtime/`, verifies checksums and does not install globally. See the setup script for exact versions and download sizes. The model runs on `127.0.0.1:8766` under the alias `catalog-qwen`. GPU support uses Vulkan; the model launcher documents the CPU option.

Use `powershell -ExecutionPolicy Bypass -File scripts/start_model.ps1 -Cpu` if Vulkan is unavailable. On other platforms, use a separately installed llama.cpp server with the same loopback address and alias; the bundled downloader supports Windows x64 only. Setup is roughly 672 MB of downloads. Once installed, inference works locally without an API key.

The application status shows whether the model is reachable. A failed model request displays an error and leaves manual mapping available. It never substitutes scripted answers and labels them AI.

## A three-minute walkthrough

1. Select **Load sample with errors**, a clearly labeled synthetic fixture with 10 records and unfamiliar headers.
2. Select **Suggest with AI** and inspect the returned column choices against the example values alongside them.
3. Confirm `Item ref` is SKU, `Display label` is product name, and `List amount` is regular price. In **Optional columns**, confirm `GTIN` is barcode and `Deal amount` is sale price. Parent SKU and description should be **Not provided**. Adjust any wrong choice.
4. Select **I have reviewed the selected columns**, then **Check for issues**. Inspect the missing price, conflicting SKU prices, exact duplicate and other exceptions.
5. Download the issue report and mapped review CSV. The latter preserves duplicate/problem rows and is not a certified Shopify or WooCommerce import file.
6. Load **WooCommerce official** to demonstrate that blank prices on variable/grouped parent records are valid.

## Deliberate boundaries

- One UTF-8 CSV at a time, comma/semicolon/tab delimiters, up to 5,000 records and 100 columns. The JSON request limit is 2 MiB, so escaped CSV content has a slightly smaller practical upload limit.
- This version requires columns for SKU, product name and regular selling price. Their headers can differ from these labels; AI proposes matches and the user confirms them. Individual cells can be blank and are checked by the relevant rules. The other seven fields are optional. Extra source columns are allowed but are not checked or included in the mapped export.
- Prices use a decimal point, without thousands separators or currency symbols. Ambiguous formats are flagged for review, not interpreted as a currency conversion.
- SKU identity is exact and case-sensitive within one file. Different suppliers need a deliberate namespace before being combined.
- A missing product-type mapping is treated as simple products and disclosed in report notes. Mapping the source row type matters for parent rows.
- No scraping, store credentials, live imports, image downloads, translation, subscription billing or cross-file inventory synchronization.
- The review export has ten canonical columns, leaving unmapped fields blank. Keep the original source for other source columns. Formula-like text is prefixed with an apostrophe in exported CSVs for spreadsheet safety; the in-memory source is unchanged. Import SKU and barcode columns as text in spreadsheet software to retain leading zeros.

## Why open models matter here

The application sends the local model column headers and up to three bounded sample values per column, not the complete catalog. Headers and samples are treated as untrusted data. A constrained JSON schema limits outputs to existing column names or null. Explicit GTIN/EAN/UPC/barcode headers are reserved for barcode suggestions, and explicit SKU/item-reference headers are excluded from barcode suggestions. This uses header words, never digit length or leading zeros; mixed labels such as `SKU / EAN` remain ambiguous. These constraints restrict model choices without generating substitute answers. Manual selection can override a header convention.

A second validation pass rejects unknown columns, identifier mismatches and reused columns. Every field in a duplicate assignment is cleared, rather than keeping whichever field happened to come first. The page names the source column and affected fields, explains how to correct the selection, and links to the affected dropdowns. Messages update after manual corrections, and live duplicate selections block checking. Missing optional fields do not produce warnings. You review every mapping before the deterministic checks run.

This supports a local workflow for unreleased product lists and supplier prices. There is no inference service account or per-request API charge in local mode; local compute still has a cost. Model speed and quality depend on hardware. The local model can be replaced through a compatible **loopback-only** endpoint using `CATALOG_MODEL_URL` and `CATALOG_MODEL_NAME`. Start custom local servers yourself; one-click startup manages only the bundled default server.

API mode sends the same bounded input and applies the same validation and human review. The local mode uses a constrained JSON schema during generation. API mode defaults to JSON object output, so the provider need not support schema constraints; invalid choices are rejected after generation. Choose an open model when using an API for the competition demonstration. The bundled Qwen model remains the project's actual open-model implementation.

## Data and claims

The three downloaded public CSV fixtures contain 86 records in total. They are unchanged, and retain their original licenses. The independent synthetic supplier demo is generated by `catalog_check/samples.py`. See [third-party notices](THIRD_PARTY_NOTICES.md) and the recorded source hashes in `research/2026-10-15/samples/provenance.json`.

CrossPeak's intentionally bad records include hints in their names/SKUs. They exercise deterministic rules and are not a fair model-accuracy benchmark. Public Upwork job descriptions informed the problem choice; no client dataset or customer endorsement is included. No paying user or time saving has been claimed.

## Verify

```powershell
python -m unittest discover -s tests -v
```

Tests cover legitimate parent-row blanks, missing prices, duplicate/conflicting SKUs, currency boundaries, leading zeros, malformed CSV, safe export, mapping validation, model failure, HTTP origin boundaries, API authentication and output modes, bounded sample transmission, error redaction, redirect rejection, and local startup.

To reproduce the actual model observations with the local model running:

```powershell
python scripts/evaluate_model.py
```

This writes `evidence/initial-evaluation.json` with suggested mappings, differences from manually reviewed expectations, latency, source hashes and rule reports. These four familiar samples are development smoke checks, not a held-out accuracy benchmark. Rule reports use the manually reviewed mapping so a model error cannot be mistaken for a rule failure.

Observed on October 15 with Qwen3-0.6B Q8_0 and an RTX 3060 Laptop GPU:

| Fixture | Mapping fields matching the reviewed expectation | Inference time | Rule report after human mapping |
| --- | --- | --- | --- |
| Synthetic supplier | 8 / 10 | 0.82 s | 4 errors, 6 warnings |
| WooCommerce official | 10 / 10 | 1.27 s | 0 errors, 0 warnings |
| CrossPeak normal | 9 / 10 | 1.64 s | 0 errors, 6 warnings for absent SKUs |
| CrossPeak problem | 9 / 10 | 1.64 s | 6 errors, 2 warnings |

The counts include correctly absent fields. The model confused SKU and GTIN in the synthetic sample and wrongly suggested Categories as currency in the two CrossPeak samples. Review those fields explicitly. Inference times are warm local observations, not startup times or service guarantees. Prompt variants were tried on these same examples, so these results must not be presented as independent accuracy estimates. The earlier baseline and unsuccessful few-shot experiment are retained in `evidence/`.

On October 17, the identifier constraints and conflict handling were revised. In [the later smoke check](evidence/identifier-review-final.json), the synthetic sample's SKU and barcode matched `Item ref` and `GTIN`; the complete field matches were 9/10, 8/10, 9/10 and 9/10 across the four samples. Other mistakes remain: a name/description collision in the synthetic run, and incorrect currency and barcode suggestions in the official WooCommerce run. This is a targeted identifier improvement, not an overall accuracy gain. The two intermediate prompt/constraint trials are retained in `evidence/identifier-review-evaluation*.json`. These familiar samples informed the changes and are not independent accuracy evidence. Different runs can still produce different errors.

The browser flow was exercised with the synthetic sample: model suggestions, manual correction, explicit confirmation, findings, severity filters, report assumptions and both export actions. The October 17 UI check verified that a real AI conflict names the column and fields, its Review button opens and focuses an optional field, correction removes the message, and manually duplicating `GTIN` across SKU/barcode blocks checking. Corrected mappings still produce 4 errors and 6 warnings.

On October 19, before the submission deadline, optional API inference and one-click local setup/start were added. The Python suite passes 44 tests. Browser verification exercised one-click startup, real inference in local mode, and the generic API path against the real local Qwen server using strict JSON schema. After correcting the model's Product type/Description collision, the synthetic sample still produced 4 errors and 6 warnings. Clear API settings and page reload both removed the test key. See [the smoke-check record](evidence/api-local-smoke.json) and [settings screenshot](evidence/ai-api-settings.jpg).

API protocol tests use a local mock provider; no paid external provider has been tested with a real customer key. Provider-specific compatibility must therefore be checked with **Test & use API** before relying on it. Successful connection testing confirms access and JSON output, not mapping accuracy.

The [submission materials](submission/README.md) include an English article draft and a narrated 1080p video walkthrough using real application captures. They are prepared locally, not published. The competition still requires a public repository, an accessible deployment or video link, and a published English DEV post. The deadline is October 19, 2026 at 14:59 China Standard Time. Any changes made after that deadline must be identified in this README before submission-related claims are updated.

## License

Application code: MIT. Third-party CSV fixtures, model weights and runtime binaries retain their own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
