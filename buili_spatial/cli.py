"""Command-line diagnostics and worker integration for ``python -m buili_spatial``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .analysis import build_default_analysis_service
from .contracts import finalize_plan_graph_payload
from .io_utils import atomic_write_json
from .pipeline import SpatialPipelineError, parse_pdf_to_plan_graph
from .transforms import compute_similarity_transform


def _read_json(path: str | Path) -> Any:
    candidate = Path(path).expanduser().resolve(strict=True)
    if candidate.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("JSON input exceeds the 256 MB CLI limit")
    return json.loads(candidate.read_text(encoding="utf-8"))


def _emit(payload: Any, output: str | None) -> None:
    if output:
        atomic_write_json(Path(output), payload)
    else:
        print(
            json.dumps(
                payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            )
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buili-spatial")
    parser.add_argument(
        "--version", action="version", version="buili-spatial 2026.07.1"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser(
        "validate-plan", help="validate and canonicalize PlanGraph JSON"
    )
    validate.add_argument("input")
    validate.add_argument("--output", "-o")

    align = commands.add_parser("align", help="compute a validated 2D anchor transform")
    align.add_argument("anchors", help="JSON list of {plan:[x,y],field:[x,y],label?}")
    align.add_argument("--output", "-o")

    evaluate = commands.add_parser(
        "evaluate", help="evaluate predicted plan elements against GT"
    )
    evaluate.add_argument("prediction")
    evaluate.add_argument("ground_truth")
    evaluate.add_argument("--output", "-o")

    analyze = commands.add_parser(
        "analyze", help="analyze an image, audio, or document"
    )
    analyze.add_argument("input")
    analyze.add_argument("--kind", choices=["image", "audio", "document"])
    analyze.add_argument(
        "--external", action="store_true", help="explicitly enable configured adapter"
    )
    analyze.add_argument("--output", "-o")

    parse_pdf = commands.add_parser(
        "parse-pdf", help="parse one immutable PDF page into PlanGraph"
    )
    parse_pdf.add_argument("input")
    parse_pdf.add_argument("output_dir")
    parse_pdf.add_argument("--project-id", required=True)
    parse_pdf.add_argument("--sheet-id", required=True)
    parse_pdf.add_argument("--source-doc-id", required=True)
    parse_pdf.add_argument("--source-revision-id", required=True)
    parse_pdf.add_argument("--source-revision", default="")
    parse_pdf.add_argument("--source-issue-date", default="")
    parse_pdf.add_argument("--source-hash", default="")
    parse_pdf.add_argument("--page", type=int, default=1)
    parse_pdf.add_argument("--px-per-meter", type=float, default=100.0)
    parse_pdf.add_argument("--scale-source", default="cli_unverified_default")
    parse_pdf.add_argument("--scale-confidence", type=float, default=0.2)
    parse_pdf.add_argument("--no-ocr", action="store_true")
    parse_pdf.add_argument("--output", "-o", help="canonical PlanGraph JSON output")

    glb = commands.add_parser(
        "build-glb", help="assemble a GLB from canonical PlanGraph JSON"
    )
    glb.add_argument("input")
    glb.add_argument("storage_root")
    glb.add_argument("--project-id", required=True)
    glb.add_argument("--asset-id", required=True)
    glb.add_argument("--output", "-o", help="metadata JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-plan":
            _emit(finalize_plan_graph_payload(_read_json(args.input)), args.output)
        elif args.command == "align":
            anchors = _read_json(args.anchors)
            if not isinstance(anchors, list):
                raise ValueError("anchors JSON must be a list")
            _emit(compute_similarity_transform(anchors), args.output)
        elif args.command == "evaluate":
            from .eval_metrics import evaluate_plan_elements

            _emit(
                evaluate_plan_elements(
                    _read_json(args.prediction), _read_json(args.ground_truth)
                ),
                args.output,
            )
        elif args.command == "analyze":
            service = build_default_analysis_service(allow_external=args.external)
            result = service.analyze(args.input, kind=args.kind)
            _emit(result.model_dump(mode="json"), args.output)
        elif args.command == "parse-pdf":
            payload = parse_pdf_to_plan_graph(
                args.input,
                args.output_dir,
                project_id=args.project_id,
                sheet_id=args.sheet_id,
                source_doc_id=args.source_doc_id,
                source_revision_id=args.source_revision_id,
                source_revision=args.source_revision,
                source_issue_date=args.source_issue_date,
                source_hash=args.source_hash,
                page_no=args.page,
                px_per_meter=args.px_per_meter,
                scale_source=args.scale_source,
                scale_confidence=args.scale_confidence,
                use_ocr=not args.no_ocr,
            )
            _emit(payload, args.output)
        elif args.command == "build-glb":
            from .geometry import build_design_glb

            uri, metadata = build_design_glb(
                _read_json(args.input),
                args.project_id,
                args.asset_id,
                storage_root=Path(args.storage_root),
            )
            _emit({"uri": uri, "metadata": metadata}, args.output)
        return 0
    except SpatialPipelineError as exc:
        print(json.dumps({"error": exc.to_dict()}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "SPATIAL_CLI_ERROR",
                        "message": str(exc),
                        "type": type(exc).__name__,
                    }
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
