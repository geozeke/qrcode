# Direct dependency licenses

Every production, development, test, documentation, container, and
GitHub Actions dependency must permit no-fee commercial and
non-commercial use, modification, and redistribution. Reciprocal
licenses require a separate explicit project decision.

The machine-checked inventory is stored in
[`config/dependency-licenses.toml`](https://github.com/geozeke/qrcode/blob/main/config/dependency-licenses.toml).
`just licenses` fails if a direct dependency is missing from the
inventory, a stale record remains, or a recorded license is outside the
approved set.

Approved licenses currently used by direct dependencies are:

- Apache-2.0
- BSD-2-Clause
- BSD-3-Clause
- MIT
- MIT-CMU
- PSF-2.0

License checks run in GitHub Actions and as part of `just check` locally.
The scheduled security workflow performs current vulnerability audits.
