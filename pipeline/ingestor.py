"""
PDF Ingestor — watches a directory for new PDFs and runs extraction + store.

Usage:
    python -m pipeline.ingestor               # watch mode
    python -m pipeline.ingestor --backfill    # process all existing PDFs
"""

import argparse
import sys
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.extractor import extract_pdf
from pipeline.store import upsert_record, init_db

WATCH_DIR = PROJECT_ROOT / "data" / "demo_pdfs"


class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and event.src_path.endswith(".pdf"):
            process_pdf(Path(event.src_path))


def process_pdf(pdf_path: Path) -> dict | None:
    print(f"[ingestor] Processing: {pdf_path.name}")
    try:
        record = extract_pdf(pdf_path)
        upsert_record(record)
        conf = record.get("extraction_confidence", 1.0)
        flag = " ⚠ LOW CONFIDENCE" if conf < 0.8 else ""
        print(f"[ingestor] ✓ Stored: {record['portco_name']} {record['period']} "
              f"(confidence={conf:.2f}){flag}")
        return record
    except Exception as e:
        print(f"[ingestor] ✗ Error processing {pdf_path.name}: {e}")
        return None


def backfill():
    """Process all PDFs in the watch directory."""
    init_db()
    pdfs = sorted(WATCH_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"[ingestor] No PDFs found in {WATCH_DIR}")
        return
    print(f"[ingestor] Backfilling {len(pdfs)} PDFs...")
    for pdf in pdfs:
        process_pdf(pdf)
    print("[ingestor] Backfill complete.")


def watch():
    """Watch directory for new PDFs in real-time."""
    init_db()
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(PDFHandler(), str(WATCH_DIR), recursive=False)
    observer.start()
    print(f"[ingestor] Watching {WATCH_DIR} for new PDFs... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlphaFMC PDF Ingestor")
    parser.add_argument("--backfill", action="store_true",
                        help="Process all existing PDFs then exit")
    args = parser.parse_args()

    if args.backfill:
        backfill()
    else:
        watch()
