#!/usr/bin/env python3
"""
download_data.py — Download Tesserae V6 index files

Reads DATA_MANIFEST.json and downloads pre-built search indexes
from the Tesserae data server. Run this after cloning the Git
repository to get the application ready to use.

Usage:
    python scripts/download_data.py              # Download all files
    python scripts/download_data.py --check      # Check which files are present/missing
    python scripts/download_data.py --file la     # Download only Latin index
"""

import json
import hashlib
import os
import sys
import tarfile
import urllib.request
import urllib.error
import argparse
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "DATA_MANIFEST.json")


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        print(f"Error: {MANIFEST_PATH} not found.")
        print("Make sure you're running this from the tesserae-v6 project root.")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        return json.load(f)


def file_exists_and_valid(filepath):
    if not os.path.exists(filepath):
        return False, "missing"
    return True, "ok"


def verify_checksum(filepath, expected_sha256):
    if not expected_sha256 or expected_sha256.lower() == "pending":
        return True, "checksum not yet set"
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual == expected_sha256:
        return True, "checksum verified"
    return False, f"checksum mismatch (expected {expected_sha256[:12]}..., got {actual[:12]}...)"


def format_size(size_bytes):
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    elif size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.0f} MB"
    else:
        return f"{size_bytes / 1_000:.0f} KB"


def download_with_progress(url, dest_path):
    try:
        req = urllib.request.Request(url)
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.URLError as e:
        return False, str(e)

    total = response.headers.get("Content-Length")
    total = int(total) if total else None

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    downloaded = 0
    block_size = 1024 * 1024
    with open(dest_path, "wb") as f:
        while True:
            chunk = response.read(block_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                bar_len = 40
                filled = int(bar_len * downloaded / total)
                bar = "=" * filled + "-" * (bar_len - filled)
                sys.stdout.write(f"\r  [{bar}] {pct:.1f}% ({format_size(downloaded)} / {format_size(total)})")
            else:
                sys.stdout.write(f"\r  Downloaded {format_size(downloaded)}...")
            sys.stdout.flush()

    print()
    return True, "ok"


def extract_archive(archive_path, extract_to):
    extract_dir = os.path.dirname(os.path.join(PROJECT_ROOT, extract_to))
    os.makedirs(extract_dir, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = os.path.normpath(os.path.join(extract_dir, member.name))
            if not member_path.startswith(os.path.normpath(extract_dir)):
                raise RuntimeError(
                    f"Archive contains unsafe path: {member.name}"
                )
            if member.name.startswith("/") or ".." in member.name:
                raise RuntimeError(
                    f"Archive contains unsafe path: {member.name}"
                )
        tar.extractall(path=extract_dir)

    return True


def check_status(manifest):
    print("\n=== Tesserae V6 Data File Status ===\n")

    all_ok = True
    for entry in manifest["files"]:
        filepath = os.path.join(PROJECT_ROOT, entry["extract_to"])
        exists, status = file_exists_and_valid(filepath)

        if exists:
            marker = "OK"
        else:
            marker = "MISSING"
            all_ok = False

        required = entry.get("required", True)
        req_label = " (required)" if required else " (optional)"
        size_label = entry.get("size_human") or entry.get(
            "size_uncompressed_human", "unknown size")

        print(f"  [{marker:7s}] {entry['extract_to']} — {size_label}{req_label}")
        print(f"           {entry['description']}")

    print()
    also_needed = manifest.get("notes", {}).get("also_needed", [])
    if also_needed:
        print("Also included in Git repository:")
        for item in also_needed:
            print(f"  [  OK   ] {item}")

    print()
    if all_ok:
        print("All data files are present. The application is ready to run.")
    else:
        print("Some data files are missing. Run this script without --check to download them.")
        print(f"  python scripts/download_data.py")

    return all_ok


def download_files(manifest, file_filter=None):
    base_url = manifest["base_url"].rstrip("/")

    files_to_download = manifest["files"]
    if file_filter:
        files_to_download = [
            f for f in files_to_download
            if file_filter.lower() in f["filename"].lower()
            or file_filter.lower() in f["extract_to"].lower()
            or file_filter.lower() in f["description"].lower()
        ]
        if not files_to_download:
            print(f"No files matching '{file_filter}'. Available files:")
            for f in manifest["files"]:
                print(f"  {f['filename']} — {f['description']}")
            sys.exit(1)

    total_size = sum(f.get("size_compressed") or 0 for f in files_to_download)
    print(f"\n=== Tesserae V6 Data Downloader ===\n")
    print(f"Source: {base_url}")
    print(f"Files to download: {len(files_to_download)}")
    print(f"Total download size: ~{format_size(total_size)}")
    print()

    skipped = 0
    downloaded = 0
    failed = 0

    for entry in files_to_download:
        filepath = os.path.join(PROJECT_ROOT, entry["extract_to"])
        exists, status = file_exists_and_valid(filepath)

        if exists:
            size_label = entry.get("size_uncompressed_human", "")
            print(f"SKIP: {entry['extract_to']} (already present, {size_label})")
            skipped += 1
            continue

        url = f"{base_url}/{entry['filename']}"
        archive_path = os.path.join(PROJECT_ROOT, ".tmp_download", entry["filename"])
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)

        dl_size = entry.get("size_compressed_human", "unknown size")
        print(f"Downloading: {entry['filename']} ({dl_size} compressed)")
        print(f"  From: {url}")

        ok, msg = download_with_progress(url, archive_path)
        if not ok:
            print(f"  FAILED: {msg}")
            failed += 1
            continue

        sha256 = entry.get("sha256", "")
        if sha256 and sha256.lower() != "pending":
            print(f"  Verifying checksum...", end=" ")
            ok, msg = verify_checksum(archive_path, sha256)
            if ok:
                print(msg)
            else:
                print(f"FAILED: {msg}")
                os.remove(archive_path)
                failed += 1
                continue

        print(f"  Extracting to {entry['extract_to']}...")
        try:
            extract_archive(archive_path, entry["extract_to"])
            print(f"  Done.")
            downloaded += 1
        except Exception as e:
            print(f"  FAILED to extract: {e}")
            failed += 1
            continue

        os.remove(archive_path)

    tmp_dir = os.path.join(PROJECT_ROOT, ".tmp_download")
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    print(f"\n=== Summary ===")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped (already present): {skipped}")
    if failed:
        print(f"  Failed: {failed}")
    print()

    if failed:
        print("Some downloads failed. You can retry by running this script again.")
        print("Files that were already downloaded will be skipped.")
        sys.exit(1)
    else:
        print("All data files are ready. Start the application with: python main.py")


def main():
    parser = argparse.ArgumentParser(
        description="Download Tesserae V6 search index files"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check which files are present/missing without downloading"
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="Download only files matching this string (e.g., 'la' for Latin, 'grc' for Greek)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if files already exist"
    )
    args = parser.parse_args()

    manifest = load_manifest()

    if args.check:
        check_status(manifest)
    else:
        if args.force:
            for entry in manifest["files"]:
                filepath = os.path.join(PROJECT_ROOT, entry["extract_to"])
                if os.path.exists(filepath):
                    os.remove(filepath)
        download_files(manifest, file_filter=args.file)


if __name__ == "__main__":
    main()
