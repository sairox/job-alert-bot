"""
State manager — persists the set of job IDs that have already triggered alerts.

Backends:
  - Local JSON file  (USE_S3=false, default) — for local dev
  - AWS S3           (USE_S3=true)           — for Lambda (state survives invocations)
"""

import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self, config):
        self.config = config
        self._seen: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        if self.config.use_s3:
            self._load_s3()
        else:
            self._load_file()
        logger.info(f"State loaded — {len(self._seen)} previously seen job IDs")

    def save(self) -> None:
        if self.config.use_s3:
            self._save_s3()
        else:
            self._save_file()
        logger.info(f"State saved — {len(self._seen)} total seen job IDs")

    def is_new(self, job_id: str) -> bool:
        return job_id not in self._seen

    def mark_seen(self, job_id: str) -> None:
        self._seen.add(job_id)

    # ------------------------------------------------------------------
    # File backend
    # ------------------------------------------------------------------

    def _load_file(self) -> None:
        path = Path(self.config.state_file)
        if not path.exists():
            self._seen = set()
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self._seen = set(data.get("seen_ids", []))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Could not read state file ({exc}); starting fresh.")
            self._seen = set()

    def _save_file(self) -> None:
        path = Path(self.config.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"seen_ids": sorted(self._seen)}, f)

    # ------------------------------------------------------------------
    # S3 backend
    # ------------------------------------------------------------------

    def _load_s3(self) -> None:
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client("s3", region_name=self.config.aws_region)
        try:
            resp = s3.get_object(Bucket=self.config.s3_bucket, Key=self.config.s3_key)
            data = json.loads(resp["Body"].read().decode("utf-8"))
            self._seen = set(data.get("seen_ids", []))
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("NoSuchKey", "NoSuchBucket"):
                logger.info("No existing state object in S3; starting fresh.")
                self._seen = set()
            else:
                raise

    def _save_s3(self) -> None:
        import boto3

        s3 = boto3.client("s3", region_name=self.config.aws_region)
        s3.put_object(
            Bucket=self.config.s3_bucket,
            Key=self.config.s3_key,
            Body=json.dumps({"seen_ids": sorted(self._seen)}).encode("utf-8"),
            ContentType="application/json",
        )
