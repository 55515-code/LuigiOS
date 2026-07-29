# LuigiOS SDK

`versions.env` pins the official CachyOS Live ISO source and its deterministic
timestamp. `package-lock.json` records the complete package closure.

Use `../tools/sdk doctor` for prerequisites and `../tools/sdk validate` for the
local gate. A release build requires the verified cache created by
`../tools/sdk fetch` and embedded by `../tools/sdk stage`; `image-dev` is
explicitly non-release.

Generated data lives under `.sdk/` and final images under `dist/`.
