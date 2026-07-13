# Fixture asset pipeline

BUILI separates spatial truth from presentation geometry.

1. `PlanGraph` owns source sheet, object type, dimensions, location, elevation, and confidence.
2. The approved spatial scene owns walls, openings, floors, and the coordinate transform back to the drawing.
3. The fixture asset layer supplies recognizable geometry only. The demo uses approved, hash-addressed GLBs for lights, receptacles, panels, sinks, casework, diffusers, returns, vanities, and air-handling equipment.
4. Curated or generated GLB assets may replace a procedural asset after validation, but they never change the PlanGraph position or contractual dimensions.

## Generated asset provider contract

The backend implements a Tripo-compatible generation adapter and fixture-asset registry. It saves every accepted output to BUILI-owned object storage and registers:

- provider and provider job ID;
- prompt and generation settings;
- immutable SHA-256 hash;
- license and review status;
- canonical units, origin, up-axis, bounds, polygon count, and texture sizes;
- approved scale and rotation for the matching semantic fixture type.

Only reviewed assets are exposed to customer projects. Remote provider URLs are never loaded directly in the browser: provider URLs expire and are treated as untrusted input. The worker validates HTTPS host/DNS resolution, redirect targets, response size/content type, GLB 2.0 structure, bounds, and face count before copying the bytes into BUILI storage. Approval additionally requires explicit geometry, orientation, material/license, and semantic-fit attestations.

The production path is:

```text
semantic fixture type + reviewed prompt
→ server-side Tripo task
→ poll pinned model version
→ download and validate GLB
→ copy to immutable BUILI storage
→ review_required
→ human approval and transform lock
→ short-lived signed manifest URL
→ Three.js viewer
```

`BUILI_TRIPO_ENABLED` is an explicit kill switch and `TRIPO_API_KEY` exists only in the API/worker secret store. The browser never receives it. Without a configured key, the public demo continues to use the BUILI-owned hash-addressed GLB library; this is intentional and keeps the demo deterministic.

The former discipline-colored debug cuboids are not part of the current public manifest. Each fixture type now resolves to a distinct GLB, with a procedural fallback used only if its approved asset cannot be fetched or parsed.
