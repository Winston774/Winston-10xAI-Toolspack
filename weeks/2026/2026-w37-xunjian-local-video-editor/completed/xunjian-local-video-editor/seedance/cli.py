from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .client import (
    KieApiError,
    KieClient,
    download_urls,
    result_urls,
    task_id_from_response,
    task_state,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        client = KieClient.from_env()
        response = run_command(client, args)
    except KieApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130

    if response is not None:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seedance",
        description="Create and inspect KIE AI Bytedance Seedance 2.0 video tasks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a Seedance task.")
    add_create_options(create)

    generate = subparsers.add_parser("generate", help="Create a task, wait for completion, and optionally download results.")
    add_create_options(generate)
    add_wait_options(generate)

    status = subparsers.add_parser("status", help="Fetch task status and raw result metadata.")
    status.add_argument("task_id")

    wait = subparsers.add_parser("wait", help="Poll task status until it reaches success or fail.")
    wait.add_argument("task_id")
    add_wait_options(wait)

    return parser


def add_create_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt", required=True, help="Text prompt for the video.")
    parser.add_argument(
        "--model",
        default="bytedance/seedance-2",
        help="KIE model id. Use bytedance/seedance-2-fast for the fast variant.",
    )
    parser.add_argument("--callback-url", help="Optional HTTPS callback URL.")
    parser.add_argument("--first-frame-url", help="Image URL for first-frame image-to-video.")
    parser.add_argument("--last-frame-url", help="Image URL for last-frame control.")
    parser.add_argument("--reference-image-url", action="append", dest="reference_image_urls", help="Reference image URL. Repeatable.")
    parser.add_argument("--reference-video-url", action="append", dest="reference_video_urls", help="Reference video URL. Repeatable.")
    parser.add_argument("--reference-audio-url", action="append", dest="reference_audio_urls", help="Reference audio URL. Repeatable.")
    parser.add_argument("--return-last-frame", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--generate-audio", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--resolution", default="720p")
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--web-search", action=argparse.BooleanOptionalAction, default=None)


def add_wait_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--poll-interval", type=int, default=5, help="Seconds between status checks.")
    parser.add_argument("--timeout", type=int, default=900, help="Maximum seconds to wait.")
    parser.add_argument("--download", action="store_true", help="Download result URLs after success.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for downloaded result files.")


def run_command(client: KieClient, args: argparse.Namespace) -> dict[str, Any] | None:
    if args.command == "create":
        response = create_task(client, args)
        response["taskId"] = task_id_from_response(response)
        return response

    if args.command == "generate":
        created = create_task(client, args)
        task_id = task_id_from_response(created)
        print(f"Created task: {task_id}", file=sys.stderr)
        response = client.wait_for_task(
            task_id,
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout,
        )
        return with_downloads(response, args)

    if args.command == "status":
        return client.get_task(args.task_id)

    if args.command == "wait":
        response = client.wait_for_task(
            args.task_id,
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout,
        )
        return with_downloads(response, args)

    raise KieApiError(f"Unknown command: {args.command}")


def create_task(client: KieClient, args: argparse.Namespace) -> dict[str, Any]:
    validate_source_mode(args)
    return client.create_task(
        prompt=args.prompt,
        model=args.model,
        callback_url=args.callback_url,
        first_frame_url=args.first_frame_url,
        last_frame_url=args.last_frame_url,
        reference_image_urls=args.reference_image_urls,
        reference_video_urls=args.reference_video_urls,
        reference_audio_urls=args.reference_audio_urls,
        return_last_frame=args.return_last_frame,
        generate_audio=args.generate_audio,
        resolution=args.resolution,
        aspect_ratio=args.aspect_ratio,
        duration=args.duration,
        web_search=args.web_search,
    )


def validate_source_mode(args: argparse.Namespace) -> None:
    has_first_or_last = bool(args.first_frame_url or args.last_frame_url)
    has_references = bool(args.reference_image_urls or args.reference_video_urls or args.reference_audio_urls)
    if has_first_or_last and has_references:
        raise KieApiError(
            "Seedance docs mark first/last-frame image-to-video and multimodal references as mutually exclusive. "
            "Use either --first-frame-url/--last-frame-url or reference URL options, not both."
        )


def with_downloads(response: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.download and task_state(response) == "success":
        urls = result_urls(response)
        files = download_urls(urls, Path(args.output_dir)) if urls else []
        response["downloadedFiles"] = [str(path) for path in files]
    return response


if __name__ == "__main__":
    raise SystemExit(main())
