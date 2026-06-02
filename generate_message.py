#!/usr/bin/env python3
"""
Standalone client question message generator.

Usage examples:
    python generate_message.py --session sessions/session_20260602_143000.json
    python generate_message.py --session sessions/session_20260602_143000.json --language he --tone casual --format sms
    python generate_message.py --idk-file idk_data.json --client-name "Roni" --language he --tone formal --format email
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from client_message import MessageOptions, generate_client_message


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a client-facing message from unanswered (IDK) questions.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--session", type=Path, help="Path to a saved session JSON file")
    source.add_argument("--idk-file", type=Path, help="Path to a JSON file with IDK questions dict")

    parser.add_argument("--language", choices=["en", "he"], default="en", help="Message language (default: en)")
    parser.add_argument("--tone", choices=["formal", "casual"], default="formal", help="Message tone (default: formal)")
    parser.add_argument("--format", choices=["sms", "email"], default="email", dest="fmt", help="Message format (default: email)")
    parser.add_argument("--client-name", default="client", help="Client name for greeting")
    parser.add_argument("--sender-name", default="", help="Your name for sign-off")
    parser.add_argument("--output", type=Path, default=None, help="Output file path (default: auto-generated)")

    args = parser.parse_args()

    if args.session:
        data = json.loads(args.session.read_text("utf-8"))
        idk_questions = data.get("_idk_questions", {})
        client_name = data.get("client_name", args.client_name)
    else:
        idk_questions = json.loads(args.idk_file.read_text("utf-8"))
        client_name = args.client_name

    if not idk_questions:
        print("No IDK questions found.")
        return

    options = MessageOptions(
        language=args.language,
        tone=args.tone,
        format=args.fmt,
        client_name=client_name,
        sender_name=args.sender_name,
    )

    output_path = args.output or Path(f"client_questions_{args.language}_{args.tone}_{args.fmt}.txt")
    message = generate_client_message(idk_questions, options, output_path)
    print(message)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
