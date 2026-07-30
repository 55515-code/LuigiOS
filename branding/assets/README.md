# Asset Drop Zone

Add generated assets at the exact relative paths declared in
`../brand-v1.json`. Directories may contain the native ES or COSMIC package layout;
do not flatten those formats.

Before committing artwork, record its author, source prompt or design source,
license, exact hash, and export settings in the central `../PROVENANCE.json`.
Generated previews, working files, and proprietary references should remain
outside release bundles.
Finished LuigiOS artwork belongs in the paths declared by `../brand-v1.json` or
`../semantic-icons-v1.json`. Do not add placeholders or vendor-derived marks.

Every image must have an exact relative path entry in `../PROVENANCE.json` before
CI will accept it. Run `../../tools/graphics-audit verify-source` after adding or
renaming art.
