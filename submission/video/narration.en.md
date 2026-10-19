# Catalog Compass demo narration

Edited walkthrough using real application captures and real local inference. Synthetic English narration. Fictional supplier data.

## Review supplier CSVs before import

Catalog Compass helps freelancers review supplier product files before import.

It finds missing prices, duplicate product codes, and conflicting records, while keeping the original file unchanged.

## A real open model runs locally

This demo uses Qwen 3, a small open-weight model, through llama.cpp on this computer.

Local mode needs no API key. Setup and startup are available from AI settings.

## Load a file and match its columns

We load the included sample: ten fictional products with unfamiliar column names.

SKU, product name, and regular price are required. The other fields are optional.

## AI suggests the meaning of each column

The model suggests Item ref for SKU, Display label for name, and List amount for price.

It receives column headers and a few short example values, not the full catalog.

## A model mistake becomes a review task

Here is a real mistake: the model used Kind for both Product type and Description.

The app clears both choices and explains exactly which column and fields conflict.

## The reviewer resolves the conflict

I select Kind as Product type and leave Description unselected.

The warning disappears. Barcode remains matched to GTIN, separately from the supplier's internal SKU.

## Confirm before checking

After reviewing the selections, I confirm the mapping and run the checks.

Python rules check the values. The model does not invent prices or delete duplicates.

## See the rows that need attention

For this sample, the reviewed mapping produces four errors and six warnings across nine rows.

These are fixture results, not an estimate of real-world accuracy.

## Inspect conflicting source values

One product code appears with prices of thirty-two and thirty-nine dollars.

The report shows both source rows, so the reviewer can ask the supplier which price is correct.

## Download a report for the handoff

Download the issue report or a mapped CSV for further review.

Problem rows are preserved. This is a review tool, not an automatic store importer.

## Or connect a compatible API

An optional API mode avoids the local-model download. Enter your provider, model, and key, then test the connection.

Samples go to that provider. The key stays in memory and is cleared when you refresh.

## A small tool for a concrete service

The service to test is simple: review one supplier file and deliver a useful exception report.

Forty-four automated tests pass. Paid demand remains unvalidated. The next step is a supervised freelancer trial.
