# Fixture asset pipeline

BUILI separates spatial truth from presentation geometry.

1. `PlanGraph` owns source sheet, object type, dimensions, location, elevation, and confidence.
2. The approved spatial scene owns walls, openings, floors, and the coordinate transform back to the drawing.
3. The fixture asset layer supplies recognizable geometry only. The demo uses deterministic procedural assets for lights, receptacles, panels, sinks, casework, diffusers, and air-handling equipment.
4. Curated or generated GLB assets may replace a procedural asset after validation, but they never change the PlanGraph position or contractual dimensions.

## Generated asset provider contract

A future Tripo or equivalent adapter must save the output to BUILI-owned object storage and register:

- provider and provider job ID;
- prompt and generation settings;
- immutable SHA-256 hash;
- license and review status;
- canonical units, origin, up-axis, bounds, polygon count, and texture sizes;
- approved scale and rotation for the matching semantic fixture type.

Only reviewed assets are exposed to customer projects. Remote provider URLs are not loaded directly in the browser. If generation fails or an asset is unapproved, the viewer falls back to the deterministic procedural asset.

The repository currently contains no active Tripo API client or credential. The prior yellow cuboids were a single debug mesh for all fixture locations; they have been replaced by the procedural asset layer while preserving source-aligned coordinates.
