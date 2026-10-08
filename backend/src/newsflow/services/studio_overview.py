"""Bounded SQL aggregates of retained history, never a live health/billing claim."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from newsflow.persistence import models


class StudioOverviewReader:
    def __init__(self, session: Session):
        self._session = session

    def _count(self, model, *conditions) -> int:
        return self._session.scalar(select(func.count()).select_from(model).where(*conditions))

    def _usage(self, operation, usage, job, foreign_key):
        records, inputs, cached, outputs, cost, unknown = self._session.execute(
            select(
                func.count(usage.id),
                func.coalesce(func.sum(usage.input_tokens), 0),
                func.coalesce(func.sum(usage.cached_tokens), 0),
                func.coalesce(func.sum(usage.output_tokens), 0),
                func.sum(usage.estimated_cost_usd),
                func.coalesce(func.sum(case((usage.estimated_cost_usd.is_(None), 1), else_=0)), 0),
            )
        ).one()
        observed = (
            select(foreign_key.label("job_id"), func.count(usage.id).label("records"))
            .group_by(foreign_key)
            .subquery()
        )
        known = func.coalesce(observed.c.records, 0)
        attempts, unobserved = self._session.execute(
            select(
                func.coalesce(func.sum(job.attempts), 0),
                func.coalesce(
                    func.sum(case((job.attempts > known, job.attempts - known), else_=0)), 0
                ),
            )
            .select_from(job)
            .outerjoin(observed, observed.c.job_id == job.id)
        ).one()
        return {
            "operation": operation,
            "records": records,
            "input_tokens": inputs,
            "cached_tokens": cached,
            "output_tokens": outputs,
            "known_estimated_cost_usd": format(
                Decimal(cost or 0).quantize(Decimal("0.0000000001")), "f"
            ),
            "unknown_cost_records": unknown,
            "durable_attempts": attempts,
            # PG SUM(bigint) is NUMERIC (psycopg Decimal), unlike SQLite.
            # This sum contains only integral counts; keep JSON a counter,
            # not a Decimal-serialized string. Monetary estimates stay exact.
            "unobserved_attempts": int(unobserved),
        }

    def read(self, *, now: datetime) -> dict[str, object]:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Overview time must be timezone-aware")
        return {
            "scope": "ALL_RETAINED_HISTORY",
            "generated_at": now.astimezone(UTC).isoformat(),
            "network_checked": False,
            # A committed attempt can precede an RPC or an unobserved crash.
            # Known usage and estimated price never constitute a complete invoice.
            "billing_complete": False,
            "configuration": {
                "accounts": self._count(models.TelegramAccount),
                "donors": self._count(models.DonorChannel),
                "output_channels": self._count(models.OutputChannel),
                "mappings": self._count(models.ChannelMappingModel),
            },
            "history": {
                "source_posts": self._count(models.IncomingPostModel),
                "source_revisions": self._count(models.ContentRevisionModel),
                "rewrite_jobs": self._count(models.RewriteJobModel),
                "active_rewrite_jobs": self._count(
                    models.RewriteJobModel,
                    models.RewriteJobModel.state.in_(("QUEUED", "DISPATCHED", "RUNNING", "RETRY")),
                ),
                "acknowledged_publications": self._count(
                    models.PublicationJobModel, models.PublicationJobModel.state == "SUCCEEDED"
                ),
                "uncertain_publications": self._count(
                    models.PublicationJobModel,
                    models.PublicationJobModel.state == "NEEDS_RECONCILIATION",
                ),
            },
            "usage": [
                self._usage(
                    "REWRITE",
                    models.RewriteUsageModel,
                    models.RewriteJobModel,
                    models.RewriteUsageModel.rewrite_job_id,
                ),
                self._usage(
                    "SEMANTIC_VERIFICATION",
                    models.SemanticVerificationUsageModel,
                    models.SemanticVerificationJobModel,
                    models.SemanticVerificationUsageModel.verification_job_id,
                ),
            ],
        }
