# LED model power registry

The registry only assigns a rated power when the BLE code identifies the product size or the model has one fixed
rating. Product values were checked against Chihiros product pages and specification images on 2026-07-20. A blank
value is intentional and must not be inferred from a controller or a visually similar lamp.

| Model | BLE code(s) | Rated power (W) | Source/status |
| --- | --- | --- | --- |
| Z Light TINY | `DYSSD`, `DYZSD` | 6 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-z-light-tiny-led-light) |
| Tiny Terrarium Egg | `DYDD` | 10 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-tiny-terrarium-egg) |
| A II | `DYNA2`, `DYNA2N` | 301: 15; 351/361/401: 18; 451: 21; 501: 25; 601: 28; 801/901: 40; 1201: 58 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-a-ii-led-light); size must be locally recognizable |
| WRGB II | `DYNT90`, `DYNW30/45/60/90/12P`, generic codes | 30: 33; 45: 49; 60: 67; 90: 100; 120: 130 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-led-light); generic code has no automatic value |
| WRGB II Pro | `DYWPRO30/45/60/80/90`, `DYWPR120` | 30: 37; 45: 56; 60: 74; 80: 100; 90: 110; 120: 138 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-pro-led-light) |
| WRGB II Slim | `DYSL30/45/60/90/120`, generic codes | 30: 23; 45: 35; 60: 45; 90: 69; 120: 90 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-slim-led-light); generic code has no automatic value |
| WRGB VIVID III | `DYVVD3` | — | official model/upstream fan support confirmed; no reliable device variant rating |
| C II | `DYNC2N` | 16 | [official product family](https://www.chihirosaquaticstudio.com/collections/chihiros-c-ii-led-lighting-system) |
| C II RGB | `DYNCRGP`, `DYNCRGB` | 20 | [official product page](https://www.chihirosaquaticstudio.com/products/chihiros-c-ii-rgb-led-light) |
| Universal WRGB | `DYU550/600/700/800/920/1000/1200/1500` | 28/29/33/36/55/59/91/100 | empirical local profile; not an official specification |
| Commander 1/4 | `DYCOM`, `DYLED` | — | controller only; connected lamp determines power |

For a known rating `P`, channel count `n`, and channel percentage `c`, the linear per-channel estimate is
`P / n × c / 100`. Total linear consumption is `P × average(channel percentages) / 100`, capped at `P`. Universal
WRGB instead uses the retained measured interpolation profile. These values are estimates, not power-meter readings.
