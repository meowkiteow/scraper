"""
Subprocess scraper runner.
Runs scrape_google_maps in a clean Python process to avoid Windows event-loop
conflicts (NotImplementedError when Playwright async runs inside a thread).

Usage:
    python scraper_runner.py <json_config_path>

The config JSON contains:
    keyword, location, limit, extract_emails, extract_phone, extract_website,
    extract_reviews, output_path, status_path

Results are written incrementally to output_path (JSON array).
Status updates are written to status_path (JSON object with "progress" key).
"""

import asyncio
import json
import sys
import os


def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper_runner.py <config.json>", file=sys.stderr)
        sys.exit(1)

    config_path = sys.argv[1]
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    output_path = config["output_path"]
    status_path = config["status_path"]
    stop_path = config.get("stop_path", "")

    # Write initial status
    _write_json(status_path, {"progress": "Starting headless browser...", "done": False, "error": None})
    _write_json(output_path, [])

    from scraper import scrape_google_maps

    results_so_far = []

    def status_cb(msg, progress=None):
        _write_json(status_path, {"progress": msg, "done": False, "error": None})

    def result_cb(result):
        normalized = {
            "name": result.get("Name", ""),
            "phone": result.get("Phone", ""),
            "website": result.get("Website", ""),
            "email": result.get("Emails", ""),
            "rating": result.get("Rating", ""),
            "reviews": result.get("Total Reviews", ""),
        }
        results_so_far.append(normalized)
        _write_json(output_path, results_so_far)

    def stop_check():
        if stop_path and os.path.exists(stop_path):
            return True
        return False

    try:
        results = asyncio.run(
            scrape_google_maps(
                keyword=config["keyword"],
                location=config["location"],
                limit=config["limit"],
                status_callback=status_cb,
                result_callback=result_cb,
                extract_emails=config.get("extract_emails", True),
                extract_phone=config.get("extract_phone", True),
                extract_website=config.get("extract_website", True),
                extract_reviews=config.get("extract_reviews", True),
                stop_check=stop_check,
                skip_names=config.get("skip_names", []),
            )
        )

        # If callbacks didn't fire, populate from return value
        if not results_so_far and results:
            for r in results:
                results_so_far.append({
                    "name": r.get("Name", ""),
                    "phone": r.get("Phone", ""),
                    "website": r.get("Website", ""),
                    "email": r.get("Emails", ""),
                    "rating": r.get("Rating", ""),
                    "reviews": r.get("Total Reviews", ""),
                })
            _write_json(output_path, results_so_far)

        total = len(results_so_far)
        was_stopped = stop_path and os.path.exists(stop_path)
        msg = f"{'Stopped' if was_stopped else 'Done'}! Found {total} businesses."
        _write_json(status_path, {"progress": msg, "done": True, "error": None})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        total = len(results_so_far)
        if total > 0:
            _write_json(status_path, {"progress": f"Stopped with {total} results.", "done": True, "error": None})
        else:
            _write_json(status_path, {"progress": f"Error: {str(e) or repr(e)}", "done": True, "error": str(e) or repr(e)})


def _write_json(path, data):
    """Atomically write JSON to a file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    # Atomic rename (works on Windows for same-directory)
    try:
        os.replace(tmp, path)
    except OSError:
        # Fallback: direct write
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
