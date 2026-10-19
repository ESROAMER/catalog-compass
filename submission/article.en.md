---
title: Catalog Compass helps freelancers review supplier CSVs with local AI
published: true
tags: devchallenge, hf26challenge, opensource
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).*

## What I Built

A supplier sends a spreadsheet with columns called `Item ref`, `Display label`, `List amount`, and `GTIN`. Before an import, someone has to decide what those columns mean, notice the missing price, and work out why the same product code appears with two different prices.

Catalog Compass is a small tool for that review. An open-weight model suggests column matches. A person confirms them. Python rules then flag missing prices, duplicate product codes, and conflicting records, with the affected rows and original values.

The intended user is a freelancer preparing supplier files for an online store, or a small merchant doing that work themselves. The deliverable is concrete: a CSV issue report to discuss with the supplier and a mapped CSV for the next step in the import process. The original file stays unchanged.

Public freelance job descriptions helped identify this workflow. Complete catalog-import jobs can include variants, images, translations, and store-specific updates. Catalog Compass focuses on reviewing one supplier CSV and preparing its findings for the next step.

A freelancer could use it to offer a focused service: reviewing one supplier file, resolving exceptions, and preparing a checked handoff.

## Demo

[Watch or download the narrated walkthrough (MP4)](https://github.com/ESROAMER/catalog-compass/blob/master/submission/video/catalog-compass-demo.mp4).

The video uses real application captures and real local inference. It is edited for explanation, with synthetic English narration. Its ten-product supplier file is fictional and included with the project.

You can reproduce the workflow:

1. Open the app and select **Load sample with errors**.
2. Select **Suggest with AI**. Review the column choices beside their example values.
3. Confirm `Item ref` as SKU, `Display label` as product name, and `List amount` as regular price. Under optional fields, `GTIN` is the barcode and `Kind` is the product type. Leave absent fields unselected.
4. Confirm that you have reviewed the choices, then select **Check for issues**.
5. Review the **4 errors and 6 warnings affecting 9 of 10 rows**, then download the report or mapped CSV.

## Code

[Source code and setup instructions](https://github.com/ESROAMER/catalog-compass).

I started the repository on October 15, 2026, during this challenge. The application code and fictional demo data use the MIT license. Public WooCommerce and CrossPeak fixtures retain their licenses and recorded source hashes in the repository.

The web app requires Python 3.11 or later and a browser, with no pip or npm dependencies. On Windows, double-click **Start Catalog Compass.cmd**, or run:

```powershell
python app.py --open
```

In **AI settings**, local mode offers a setup/start button. The first Windows x64 setup downloads about 672 MB of model and runtime files; later starts reuse them. A CPU option is available when GPU startup fails.

An optional API mode accepts a compatible Chat Completions endpoint, model ID, and key. It removes the local-model download requirement. The competition demo uses the local open model.

## How I Built It

The stack is deliberately small: plain HTML, CSS, and JavaScript; a Python standard-library HTTP server; [llama.cpp](https://github.com/ggml-org/llama.cpp); and [Qwen3-0.6B-GGUF in Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF).

The model has one job: infer the meaning of unfamiliar columns from their headers and a few examples. Each request contains at most three values per column, capped at 100 characters each. It does not need the complete catalog to propose a mapping.

The local generation schema restricts each answer to an existing header or `null`. Unambiguous GTIN, EAN, UPC, or barcode headers are excluded from SKU suggestions. Unambiguous SKU or item-reference headers are excluded from barcode suggestions; mixed labels still need review. These constraints use header meaning, not the length of a number: an internal product code can also contain leading zeros.

A second validation step checks the model's answer. Unknown columns and identifier mismatches are rejected. If two fields claim the same column, **both selections are cleared**. The application does not silently choose a winner based on field order.

That last rule came from a visible failure. In the demonstrated run, the model assigned `Kind` to both Product type and Description. The interface named the column and the two fields, explained the conflict, and provided buttons to review them. Selecting `Kind` for Product type and leaving Description unselected resolved it. The model's mistake became a specific decision the reviewer could inspect.

Only after confirmation do deterministic checks run. Prices are parsed and compared by code; duplicates are grouped by exact SKU; conflicting values are reported against their source rows. The model does not invent a missing price or silently remove a duplicate product.

This boundary also makes testing useful. The current **44-test suite** covers CSV parsing, legitimate blank prices on parent products, missing values, duplicate and conflicting SKUs, leading zeros, safe exports, mapping validation, and API error handling. The synthetic fixture produces the same report after manual confirmation in both inference modes.

Codex assisted with implementation, testing, and preparing this write-up.

### Working with supplier files

The app accepts one UTF-8 CSV with up to 5,000 records and 100 columns, within a 2 MiB request limit. SKU, name, and regular-price columns are required in this version; other fields are optional. Extra columns may be present, but the mapped export includes only the selected canonical fields.

The mapped CSV retains flagged rows for human review and preparation for the next import step. Prices use decimal-point notation without currency symbols or thousands separators. SKU identity is exact and case-sensitive within one file.

## Why Does Open Innovation Matter?

Supplier prices and unreleased product lists can be sensitive. With the bundled model installed, local inference keeps the column samples on the reviewer's computer and requires no inference-service account. That makes a private, repeatable review possible on the hardware already used for spreadsheet work.

Qwen's open weights and the open-source inference runtime also let me inspect the request, constrain its output, and replace the model. The rules and review interface remain usable when the model changes. Local inference has hardware, electricity, and installation costs, but no per-request provider bill.

The API option lets users run inference through a compatible service. It makes the destination visible and asks the user to allow column samples to be sent to the chosen provider. Keys stay in page memory and are cleared by refresh or the clear-settings button. Both modes share the same mapping review and rule-based checks, so users can choose where inference runs while keeping the same review workflow.
