# Third-party notices

The application code and independently authored synthetic supplier demo are MIT licensed. The following items retain separate licenses; the application license does not relicense them.

| Component | Source | License |
| --- | --- | --- |
| WooCommerce official sample CSV | https://github.com/woocommerce/woocommerce/tree/trunk/plugins/woocommerce/sample-data | GPL-2.0-or-later; retained in `research/2026-10-15/samples/woocommerce-LICENSE.txt` |
| CrossPeak good/bad sample CSVs and README | https://github.com/crosspeaksoftware/sample-data-woocommerce | GPL-2.0; retained in `research/2026-10-15/samples/crosspeak-LICENSE.txt` |
| Qwen3-0.6B-GGUF | https://huggingface.co/Qwen/Qwen3-0.6B-GGUF | Apache-2.0; downloaded separately into ignored `.runtime/` |
| llama.cpp | https://github.com/ggml-org/llama.cpp | MIT; downloaded separately into ignored `.runtime/` |

Downloaded public fixtures are unmodified. Their URLs, retrieval date, byte counts and SHA256 checksums are in `research/2026-10-15/samples/provenance.json`. Product image URLs are data only: this application does not fetch or display those images.

CrossPeak's problem records contain deliberate defects. Their names and SKUs disclose issue hints. They are used to exercise deterministic validation, not to claim model accuracy. These fixtures are not original client data and contain no evidence of a paying customer.

The independently authored supplier demo contains fictional product names, identifiers and prices. Public job descriptions informed the problem selection, not the contents of customer files. No Upwork client dataset is included.
