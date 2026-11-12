# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Persistent Human Review Store for ReqTrace.
Implements an event-sourced, append-only overlay store (.reqtrace/reviews.jsonl)
that survives link re-computations and guarantees Git 3-way conflict-free mergeability.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from filelock import FileLock
from reqtrace.models.trace_link import ReviewEvent, ReviewStatus, TraceLink
from reqtrace.models.requirement import Requirement


class ReviewStore:
    def __init__(self, store_path: Optional[Path | str] = None) -> None:
        self.store_path = (
            Path(store_path) if store_path else Path(".reqtrace/reviews.jsonl")
        )

    def _ensure_dir(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def append_event(self, event: ReviewEvent) -> None:
        """
        Appends an immutable review event to the JSONL store, strictly ending with a newline.
        Protected by FileLock to ensure multi-process concurrency safety.
        """
        self._ensure_dir()
        lock_path = self.store_path.with_suffix(".lock")
        lock = FileLock(str(lock_path), timeout=10.0)
        with lock:
            with open(self.store_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")

    def load_events(self) -> List[ReviewEvent]:
        """
        Loads all review events in chronological order, deduplicating on event_id
        and safely skipping/quarantining malformed lines.
        """
        if not self.store_path.exists():
            return []

        seen_event_ids: Set[str] = set()
        events: List[ReviewEvent] = []
        with open(self.store_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = ReviewEvent.model_validate_json(line)
                        if event.event_id not in seen_event_ids:
                            seen_event_ids.add(event.event_id)
                            events.append(event)
                    except Exception:
                        # Skip corrupted lines gracefully without crashing the pipeline
                        continue
        return events

    def get_latest_reviews(self) -> Dict[Tuple[str, str], ReviewEvent]:
        """
        Materializes the latest ReviewEvent per (req_id, test_id) key.
        Because events are append-only and timestamped, (timestamp, event_id) resolves
        independent concurrent reviews cleanly without line-level merge conflicts.
        """
        events = self.load_events()
        latest_map: Dict[Tuple[str, str], ReviewEvent] = {}

        for event in events:
            key = (event.req_id, event.test_id or "")
            if key not in latest_map:
                latest_map[key] = event
            else:
                current = latest_map[key]
                if (event.timestamp, event.event_id) > (current.timestamp, current.event_id):
                    latest_map[key] = event

        return latest_map

    def get_requirement_waivers(self) -> Dict[str, ReviewEvent]:
        """
        Materializes requirement-level review waivers (where test_id is empty or None).
        """
        latest = self.get_latest_reviews()
        return {
            req_id: event
            for (req_id, test_id), event in latest.items()
            if not test_id or event.status == ReviewStatus.WAIVED_ANALYSIS
        }

    def apply_overlay(
        self,
        links: List[TraceLink],
        requirements: Optional[Dict[str, Requirement]] = None,
    ) -> List[TraceLink]:
        """
        Merges persistent human reviews onto newly computed trace links.
        Also evaluates whether a review is stale because the requirement's content hash changed.
        """
        latest_reviews = self.get_latest_reviews()
        updated_links: List[TraceLink] = []

        for link in links:
            key = (link.req_id, link.test_id or "")
            if key in latest_reviews:
                review = latest_reviews[key]
                link.review_status = review.status
                link.reviewed_by = review.reviewed_by
                link.review_comment = review.comment
                link.review_timestamp = review.timestamp

                # Check staleness if requirement sha256 or content hash is tracked
                if requirements and link.req_id in requirements:
                    current_req = requirements[link.req_id]
                    if (
                        review.req_content_hash
                        and review.req_content_hash != current_req.sha256
                    ):
                        link.is_stale = True
                    elif (
                        review.req_sha256_at_review
                        and review.req_sha256_at_review != current_req.sha256
                    ):
                        link.is_stale = True

            updated_links.append(link)

        return updated_links
