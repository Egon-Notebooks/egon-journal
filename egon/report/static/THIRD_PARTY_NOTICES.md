# Third-party assets bundled in egon/report/static

These files are inlined into every generated HTML report so that reports work
fully offline.

| Asset | Version | Licence | Source |
|---|---|---|---|
| `vendor/vega.min.js` | 6.2.0 | BSD-3-Clause | https://github.com/vega/vega |
| `vendor/vega-lite.min.js` | 6.4.1 | BSD-3-Clause | https://github.com/vega/vega-lite |
| `vendor/vega-embed.min.js` | 7.0.2 | BSD-3-Clause | https://github.com/vega/vega-embed |
| `fonts/cormorant-garamond-*.woff2` | Fontsource 5 | SIL OFL 1.1 (`fonts/OFL-Cormorant-Garamond.txt`) | https://fontsource.org/fonts/cormorant-garamond |
| `fonts/dm-sans-*.woff2` | Fontsource 5 | SIL OFL 1.1 (`fonts/OFL-DM-Sans.txt`) | https://fontsource.org/fonts/dm-sans |

The Vega versions must match what Altair targets (`altair.VEGALITE_VERSION`).
To upgrade: download the matching `build/*.min.js` files from jsDelivr and
update this table.
