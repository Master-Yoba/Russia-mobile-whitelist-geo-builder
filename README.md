# Russia Mobile Whitelist — sing-box geo builder

Automatically builds [sing-box](https://github.com/SagerNet/sing-box) binary rule-set (`.srs`) files from the community-maintained [Russia mobile internet whitelist](https://github.com/hxehex/russia-mobile-internet-whitelist).

Two rule sets are produced on every run:

| File | Type | Contents |
|------|------|----------|
| `russia-mobile-whitelist-domains.srs` | `domain_suffix` | Domains and all their sub-domains |
| `russia-mobile-whitelist-cidr.srs` | `ip_cidr` | IP subnets (CIDR) and individual IPs |

JSON source files (`.json`) are published alongside each `.srs` for inspection or manual recompilation.

---

## Download

**Latest release** — always points to the most recent build:

```
https://github.com/Master-Yoba/Russia-mobile-whitelist-geo-builder/releases/latest/download/russia-mobile-whitelist-domains.srs
https://github.com/Master-Yoba/Russia-mobile-whitelist-geo-builder/releases/latest/download/russia-mobile-whitelist-cidr.srs
```

**Release branch** — raw files committed directly, suitable for `raw.githubusercontent.com` URLs:

```
https://raw.githubusercontent.com/Master-Yoba/Russia-mobile-whitelist-geo-builder/release/russia-mobile-whitelist-domains.srs
https://raw.githubusercontent.com/Master-Yoba/Russia-mobile-whitelist-geo-builder/release/russia-mobile-whitelist-cidr.srs
```

Dated releases are retained for 7 days; older ones are pruned automatically.

---

## sing-box configuration

Add the rule sets as remote sources inside `route.rule_set`:

```json
{
  "route": {
    "rule_set": [
      {
        "tag": "russia-domains",
        "type": "remote",
        "format": "binary",
        "url": "https://github.com/Master-Yoba/Russia-mobile-whitelist-geo-builder/releases/latest/download/russia-mobile-whitelist-domains.srs",
        "download_detour": "direct"
      },
      {
        "tag": "russia-cidr",
        "type": "remote",
        "format": "binary",
        "url": "https://github.com/Master-Yoba/Russia-mobile-whitelist-geo-builder/releases/latest/download/russia-mobile-whitelist-cidr.srs",
        "download_detour": "direct"
      }
    ],
    "rules": [
      {
        "rule_set": ["russia-domains", "russia-cidr"],
        "outbound": "direct"
      }
    ]
  }
}
```

---

## Build locally

Python 3.9+ is required. No third-party packages are needed.

```bash
python build.py
```

`sing-box` is located automatically:

1. `$SING_BOX` environment variable
2. System `PATH`
3. Previously downloaded binary in `.sing-box-bin/`
4. Downloaded automatically from the [sing-box releases](https://github.com/SagerNet/sing-box/releases) page

Pass `--no-download` to skip the automatic download and fail instead if `sing-box` is not found.

Output files are written to `output/`.

---

## CI/CD

The workflow (`.github/workflows/build.yml`) runs daily at 03:00 UTC and can also be triggered manually. It is split into three sequential jobs:

```
build  ──►  release  ──►  prune
```

| Job | What it does |
|-----|-------------|
| **build** | Fetches upstream lists, compiles `.srs` files, commits them to the `release` branch |
| **release** | Publishes a dated GitHub Release (`YYYY-MM-DD`) with all four output files attached |
| **prune** | Deletes releases older than the 7 most recent |

Each job only starts if the previous one completed successfully.

---

## Sources

- Domain and IP lists: [hxehex/russia-mobile-internet-whitelist](https://github.com/hxehex/russia-mobile-internet-whitelist)
- sing-box: [SagerNet/sing-box](https://github.com/SagerNet/sing-box)
