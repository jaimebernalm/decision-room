"""Versioned rendering contract; never inferred from report-controlled HTML."""
# Kept equal to presentation.POLICY_VERSION until the two F4 branches integrate.
POLICY_VERSION = 'v1-frame-noscript-1'
RENDERER_VERSION = 'v1-container-raster-1'
DERIVED_VERSION = 1
MAX_TEXT = 1_000_000
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024
MAX_INVENTORY_BYTES = 16 * 1024 * 1024
