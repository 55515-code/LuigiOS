# LuigiOS Beta Automation Suite

Comprehensive automation toolkit for polishing, research, and QA processes to advance LuigiOS toward production quality.

## Overview

The beta automation suite provides end-to-end validation and optimization for LuigiOS releases, covering:

- **Product Contract Validation** - Ensures product boundaries and constraints are met
- **Package Lock Integrity** - Validates reproducible package dependencies
- **Cromite Integration** - Verifies browser integration and default settings
- **Unit Tests** - Runs comprehensive test suite (40+ tests)
- **Recovery Simulation** - Tests recovery and preservation workflows
- **Design Token Validation** - Validates brand assets and design tokens
- **Asset Optimization** - Checks and optimizes image assets for size and format
- **Accessibility Compliance** - Validates WCAG color contrast and accessibility
- **Brand Consistency** - Ensures consistent LuigiOS branding across all assets
- **Upstream Tracking** - Monitors package freshness and security advisories
- **Release Readiness Scoring** - Calculates overall release readiness percentage
- **CI Checks** - Syntax validation and integration testing

## Usage

### Run Full Automation Suite

```bash
./tools/beta-automation
```

This runs all 12 checks and provides a readiness score. Exit codes:
- `0` - Ready for release (≥80% for beta, ≥95% for production)
- `1` - Not ready, address failing checks

### Individual Tools

#### Polishing Tools

```bash
# Validate design tokens and brand manifest
python tools/polish/design-tokens-validate

# Optimize and validate image assets
python tools/polish/asset-optimize

# Validate brand consistency
python tools/polish/brand-consistency
```

#### QA Tools

```bash
# Accessibility compliance check
python tools/qa/accessibility-check

# Release readiness scoring
python tools/qa/release-readiness

# Functional testing (requires KVM)
./tools/qa/functional-test --image dist/luigios-*.iso

# Hardware testing
./tools/qa/hardware-test
```

#### Research Tools

```bash
# Track upstream packages and security
python tools/research/upstream-tracker
```

## Tool Details

### design-tokens-validate

Validates `branding/design-tokens-v1.json` and `branding/manifest-v2.json`:
- Color format validation (hex colors)
- Spacing and typography validation
- Asset reference validation
- Brand manifest structure validation

### asset-optimize

Optimizes and validates image assets:
- File size threshold checks (wallpapers ≤2MB, icons ≤100KB, logos ≤500KB)
- SVG structure validation
- PNG optimization with optipng/pngquant (if available)
- SVG optimization with svgo (if available)

**Usage:**
```bash
# Check only
python tools/polish/asset-optimize

# Check and optimize
python tools/polish/asset-optimize --optimize
```

### accessibility-check

Validates accessibility compliance:
- WCAG 2.0 color contrast ratios (AA: 4.5:1, AAA: 7.0:1)
- Icon accessibility (title/aria-label presence)
- Font size minimums (12px minimum, 14px recommended)
- Touch target sizes (32px minimum, 44px recommended)
- Keyboard navigation support

### brand-consistency

Ensures brand consistency across all assets:
- Legacy term detection (batocera, steam deck, gamescope, etc.)
- LuigiOS branding validation (hostname, boot entries, installer)
- COSMIC desktop exclusivity validation
- Package naming consistency
- Recovery UI branding

### upstream-tracker

Tracks upstream packages and security:
- Package lock freshness (warns if >30 days old)
- Forbidden package validation
- AUR package status tracking
- Product contract consistency
- Security tooling configuration

### release-readiness

Calculates overall release readiness:
- Runs all validation checks
- Scores each check (pass/fail)
- Calculates percentage readiness
- Generates JSON report at `.sdk/release-readiness-report.json`
- Determines beta (≥80%) vs production (≥95%) readiness

## Automation Workflow

### Pre-Release Checklist

1. **Run full automation suite:**
   ```bash
   ./tools/beta-automation
   ```

2. **Review report:**
   ```bash
   cat .sdk/release-readiness-report.json
   ```

3. **Address any failing checks:**
   - Fix product contract violations
   - Update package lock if stale
   - Resolve accessibility issues
   - Optimize oversized assets
   - Remove legacy terms

4. **Re-run automation:**
   ```bash
   ./tools/beta-automation
   ```

5. **Commit and tag release:**
   ```bash
   git add -A
   git commit -m "Release 0.2.0 - 100% automation readiness"
   git tag v0.2.0
   ```

### CI Integration

The automation suite integrates with CI via `tools/ci-check`, which runs:
- Unit tests
- Package lock validation
- Product validation
- Cromite validation
- Syntax checks for all scripts
- Recovery simulation

### GitHub Actions

The `.github/workflows/beta.yml` workflow runs the full automation suite on:
- Push to main/develop branches
- Pull requests
- Manual dispatch with mode selection (fast/deep/release-readiness)

## Extending the Suite

### Adding New Checks

1. Create tool in appropriate directory:
   - `tools/polish/` - Asset and brand polishing
   - `tools/qa/` - Quality assurance checks
   - `tools/research/` - Upstream tracking and research

2. Implement validation logic:
   ```python
   #!/usr/bin/env python3
   import sys
   
   errors = []
   
   def error(msg):
       errors.append(msg)
   
   def validate():
       # Your validation logic
       pass
   
   def main():
       validate()
       if errors:
           for err in errors:
               print(f"error: {err}", file=sys.stderr)
           return 1
       print("✓ Validation passed")
       return 0
   
   if __name__ == "__main__":
       sys.exit(main())
   ```

3. Add to `tools/beta-automation`:
   ```bash
   run_check "check-name" \
       "python tools/category/check-name" \
       "Description of check"
   ```

4. Make executable:
   ```bash
   chmod +x tools/category/check-name
   ```

### Adding New Asset Types

Update `tools/polish/asset-optimize`:

```python
def validate_new_asset_type():
    asset_dir = ROOT / "branding" / "assets" / "new-type"
    if not asset_dir.exists():
        return
    
    for png in asset_dir.glob("*.png"):
        check_file_size(png, MAX_SIZE, "new asset")
        if "--optimize" in sys.argv:
            optimize_png(png)
```

## Reports and Artifacts

All tools generate reports in `.sdk/`:

- `release-readiness-report.json` - Overall readiness score
- `functional-test-report.json` - Functional test results
- `accessibility-report.json` - Accessibility validation results
- `asset-polish-report.json` - Asset optimization results

Reports follow a consistent schema:

```json
{
  "schema": 1,
  "kind": "luigios-<check-name>",
  "errors": 0,
  "warnings": 0,
  "error_details": [],
  "warning_details": []
}
```

## Troubleshooting

### Design Token Validation Fails

**Issue:** `manifest-v2.json: missing required field`

**Solution:** Ensure manifest has required fields:
- `schema` (integer)
- `product` (string)

### Asset Optimization Not Working

**Issue:** Assets not being optimized

**Solution:** Install optimization tools:
```bash
# Arch/CachyOS
sudo pacman -S optipng pngquant svgo

# Or use pip for svgo
npm install -g svgo
```

### Accessibility Check Fails

**Issue:** Color contrast ratio below WCAG AA

**Solution:** Update `branding/design-tokens-v1.json`:
```json
{
  "color": {
    "text": "#ffffff",
    "background": "#000000"
  }
}
```

Ensure contrast ratio ≥ 4.5:1 for normal text, ≥ 3:1 for large text.

### Brand Consistency Fails

**Issue:** Legacy terms found in files

**Solution:** Remove or replace legacy terms:
- batocera → (remove)
- steam deck → (remove)
- gamescope → (remove)
- retroarch → (remove)
- emulationstation → (remove)
- fedora atomic → (remove)
- bootc → (remove)

Add file to exclusion list in `tools/polish/brand-consistency` if term is intentional.

## Performance

The full automation suite runs in ~30 seconds on modern hardware:
- Product contract: ~1s
- Package lock: ~2s
- Cromite validation: ~1s
- Unit tests: ~5s
- Recovery simulation: ~2s
- Design tokens: ~1s
- Asset optimization: ~5s
- Accessibility: ~2s
- Brand consistency: ~3s
- Upstream tracking: ~2s
- Release readiness: ~5s
- CI checks: ~1s

## Requirements

- Python 3.12+
- Bash 5.0+
- Git
- jq (for JSON processing)
- Optional: optipng, pngquant, svgo (for asset optimization)
- Optional: QEMU with KVM (for functional testing)

## License

Part of LuigiOS - GPL-3.0-or-later
