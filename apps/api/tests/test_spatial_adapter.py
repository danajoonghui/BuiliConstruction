from __future__ import annotations

import httpx

from buili_api.main import app


async def test_demo_pdf_runs_through_versioned_spatial_contract(client):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as anonymous:
        unauthenticated = await anonymous.get("/v1/spatial-runtime/capabilities")
        assert unauthenticated.status_code == 401
    login = await client.post(
        "/v1/auth/login?transport=body",
        json={"email": "jordan@demo.builiconstruction.com", "password": "ChangeMe-Demo-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    projects = (await client.get("/v1/projects", headers=headers)).json()["data"]
    project = next(item for item in projects if item["code"] == "CR-2026-017")
    capabilities = await client.get("/v1/spatial-runtime/capabilities", headers=headers)
    assert capabilities.status_code == 200
    assert capabilities.json()["data"]["contract"] == "buili.plan-graph.v2"
    solved = await client.post(
        f"/v1/projects/{project['id']}/spatial-runtime/alignment/solve",
        headers=headers,
        json={
            "plan_graph_id": "plan-graph-review-candidate",
            "anchor_pairs": [
                {"plan": [0, 0], "field": [10, -3], "label": "a"},
                {"plan": [2, 0], "field": [10, 1], "label": "b"},
                {"plan": [2, 2], "field": [6, 1], "label": "c"},
            ],
        },
    )
    assert solved.status_code == 200, solved.text
    assert solved.json()["data"]["confidence"] > 0.8
    manifest = await client.post(
        f"/v1/projects/{project['id']}/spatial-runtime/field-manifest",
        headers=headers,
        json={
            "frames": [
                {
                    "media_id": "demo-frame-1",
                    "timestamp": 1.5,
                    "rgb_uri": "evidence/demo-frame-1.jpg",
                    "blur_score": 0.9,
                }
            ]
        },
    )
    assert manifest.status_code == 200, manifest.text
    assert manifest.json()["data"]["official_use_blocked"] is True
    documents = (await client.get(f"/v1/projects/{project['id']}/documents", headers=headers)).json()["data"]
    drawing = next(item for item in documents if item["title"] == "Electrical Power Plan E1.1")
    revision_id = drawing["revisions"][0]["id"]
    submitted = await client.post(
        f"/v1/projects/{project['id']}/spatial-scenes/generate",
        headers=headers,
        json={"source_revision_id": revision_id, "options": {"use_ocr": False}},
    )
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["data"]["id"]
    await app.state.services.jobs.queue.join()
    job = await client.get(f"/v1/jobs/{job_id}", headers=headers)
    assert job.status_code == 200
    assert job.json()["data"]["status"] == "succeeded", job.text
    scenes = await client.get(f"/v1/projects/{project['id']}/spatial-scenes", headers=headers)
    assert scenes.status_code == 200
    scene = scenes.json()["data"][0]
    assert scene["source_revision_id"] == revision_id
    graphs = await client.get(f"/v1/projects/{project['id']}/plan-graphs", headers=headers)
    assert graphs.status_code == 200
    graph = graphs.json()["data"][0]
    assert graph["graph_json"]["schema_version"] == "buili.plan-graph.v2"
    assert graph["source_hash"]
    reviewed = await client.post(
        f"/v1/spatial-scenes/{scene['id']}/review",
        headers=headers,
        json={
            "attestation": "I verified drawing scale and extracted room/wall geometry against approved E1.1.",
            "scale_verified": True,
            "geometry_verified": True,
            "locked_object_ids": [],
        },
    )
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["data"]["scene"]["status"] == "approved"
    assert reviewed.json()["data"]["plan_graph"]["reviewer_id"]
