"""Durable, deterministic publication planning with no transport side effects."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    EditorialDecisionModel,
    OutputChannel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    PublicationJobModel,
    PublicationPlanModel,
    RewriteOutputModel,
)
from newsflow.services.automatic_approval import approval_is_current
from newsflow.services.mapping_filters import candidate_technical_allowed
from newsflow.services.source_revisions import source_is_current


class CandidateBlocked(PermissionError):
    """The current editorial decision cannot safely enter planning."""


class PlanValidationError(ValueError):
    """A publication-plan policy is malformed or conflicts with durable state."""


def _slots(slot_minutes: tuple[int, ...]) -> tuple[int, ...]:
    if not slot_minutes or len(slot_minutes) > 24 or len(set(slot_minutes)) != len(slot_minutes):
        raise PlanValidationError("Publication slots must be unique daily minutes")
    if any(type(minute) is not int or not 0 <= minute < 24 * 60 for minute in slot_minutes):
        raise PlanValidationError("Publication slot minute is outside the day")
    return tuple(sorted(slot_minutes))


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise PlanValidationError("Publication plan timezone is unknown") from exc


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _plan_projection(plan: PublicationPlanModel) -> dict[str, object]:
    return {
        "id": plan.id,
        "output_channel_id": plan.output_channel_id,
        "mode": plan.mode,
        "daily_limit": plan.daily_limit,
        "timezone": plan.timezone,
        "slot_minutes": tuple(int(value) for value in plan.slot_minutes.split(",") if value),
    }


def _item_projection(
    item: PlannedPublicationModel, candidate: PublicationCandidateModel
) -> dict[str, object]:
    scheduled_for = item.scheduled_for
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=UTC)
    return {
        "id": item.id,
        "candidate_id": candidate.id,
        "content_key": candidate.content_key,
        "output_channel_id": item.output_channel_id,
        "scheduled_for": scheduled_for.astimezone(UTC).isoformat(),
        "state": item.state,
    }


class PublicationPlanningService:
    """Writes only plan/candidate/slot records; it never publishes or rewrites."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_plans(self) -> list[dict[str, object]]:
        return [
            _plan_projection(plan)
            for plan in self._session.scalars(
                select(PublicationPlanModel).order_by(PublicationPlanModel.output_channel_id)
            )
        ]

    def list_publications(self, plan_id: int, day: date) -> list[dict[str, object]]:
        plan = self._session.get(PublicationPlanModel, plan_id)
        if plan is None:
            raise LookupError("Publication plan was not found")
        zone = _zone(plan.timezone)
        starts_at = datetime.combine(day, time.min, zone).astimezone(UTC)
        ends_at = datetime.combine(day, time.max, zone).astimezone(UTC)
        rows = self._session.execute(
            select(PlannedPublicationModel, PublicationCandidateModel, EditorialDecisionModel)
            .join(
                PublicationCandidateModel,
                PlannedPublicationModel.candidate_id == PublicationCandidateModel.id,
            )
            .outerjoin(
                EditorialDecisionModel,
                EditorialDecisionModel.content_key == PublicationCandidateModel.content_key,
            )
            .where(
                PlannedPublicationModel.output_channel_id == plan.output_channel_id,
                PlannedPublicationModel.scheduled_for >= starts_at,
                PlannedPublicationModel.scheduled_for <= ends_at,
            )
            .order_by(PlannedPublicationModel.scheduled_for, PlannedPublicationModel.id)
        )
        return [
            {
                **_item_projection(item, candidate),
                "editorial_allowed": (editorial_allows_rewrite(decision)),
                "source_current": source_is_current(self._session, candidate.content_key),
            }
            for item, candidate, decision in rows
        ]

    def configure_plan(
        self,
        output_channel_id: int,
        mode: str,
        daily_limit: int,
        slot_minutes: tuple[int, ...],
        timezone: str = "UTC",
    ) -> dict[str, object]:
        if mode not in {"MANUAL", "AUTOMATIC"}:
            raise PlanValidationError("Publication mode must be MANUAL or AUTOMATIC")
        if type(daily_limit) is not int or not 1 <= daily_limit <= 24:
            raise PlanValidationError("Daily publication limit must be between 1 and 24")
        slots = _slots(slot_minutes)
        if len(slots) < daily_limit:
            raise PlanValidationError("Daily limit cannot exceed configured slots")
        _zone(timezone)
        try:
            if self._session.get(OutputChannel, output_channel_id) is None:
                raise LookupError("Output channel was not found")
            plan = self._session.scalar(
                select(PublicationPlanModel).where(
                    PublicationPlanModel.output_channel_id == output_channel_id
                )
            )
            if plan is None:
                plan = PublicationPlanModel(
                    output_channel_id=output_channel_id,
                    mode=mode,
                    daily_limit=daily_limit,
                    timezone=timezone,
                    slot_minutes=",".join(str(minute) for minute in slots),
                )
                self._session.add(plan)
            else:
                plan.mode = mode
                plan.daily_limit = daily_limit
                plan.timezone = timezone
                plan.slot_minutes = ",".join(str(minute) for minute in slots)
            self._session.flush()
            result = _plan_projection(plan)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def register_candidate(
        self, output_channel_id: int, content_key: str, *, priority: int
    ) -> dict[str, object]:
        if not content_key.strip() or len(content_key) > 255 or type(priority) is not int:
            raise PlanValidationError("Candidate content key or priority is invalid")
        try:
            if self._session.get(OutputChannel, output_channel_id) is None:
                raise LookupError("Output channel was not found")
            self._require_editorial_pass(content_key)
            if not source_is_current(self._session, content_key):
                raise CandidateBlocked("SOURCE_REVISION_NOT_CURRENT_OR_MISSING")
            candidate = self._session.scalar(
                select(PublicationCandidateModel).where(
                    PublicationCandidateModel.output_channel_id == output_channel_id,
                    PublicationCandidateModel.content_key == content_key,
                )
            )
            if candidate is None:
                candidate = PublicationCandidateModel(
                    output_channel_id=output_channel_id,
                    content_key=content_key,
                    priority=priority,
                    eligible_at=datetime(1970, 1, 1, tzinfo=UTC),
                    state="READY",
                )
                self._session.add(candidate)
                self._session.flush()
            elif candidate.priority != priority:
                raise PlanValidationError("Candidate already exists with a different priority")
            result = {
                "id": candidate.id,
                "content_key": candidate.content_key,
                "priority": candidate.priority,
                "state": candidate.state,
            }
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def plan_day(
        self, plan_id: int, day: date, *, not_before: datetime | None = None
    ) -> list[dict[str, object]]:
        if not_before is not None and not_before.tzinfo is None:
            raise PlanValidationError("Planning cutoff must be timezone-aware")
        try:
            # Serialize planners for this policy so concurrent ticks share the daily quota.
            plan = self._session.scalar(
                select(PublicationPlanModel)
                .where(PublicationPlanModel.id == plan_id)
                .with_for_update()
            )
            if plan is None:
                raise LookupError("Publication plan was not found")
            zone = _zone(plan.timezone)
            self._reconcile_stale_reservations(plan, day, zone)
            existing = self._existing_for_day(plan, day, zone)
            if plan.mode == "MANUAL" or len(existing) >= plan.daily_limit:
                self._session.commit()
                return existing
            slots = tuple(int(value) for value in plan.slot_minutes.split(",") if value)
            occupied_slots = {
                datetime.fromisoformat(str(item["scheduled_for"])).astimezone(UTC)
                for item in existing
            }
            available_slots = [
                datetime.combine(day, time(minute // 60, minute % 60), zone).astimezone(UTC)
                for minute in slots
                if datetime.combine(day, time(minute // 60, minute % 60), zone).astimezone(UTC)
                not in occupied_slots
                and (
                    not_before is None
                    or datetime.combine(day, time(minute // 60, minute % 60), zone).astimezone(UTC)
                    >= not_before
                )
            ]
            candidates = self._session.scalars(
                select(PublicationCandidateModel)
                .where(
                    PublicationCandidateModel.output_channel_id == plan.output_channel_id,
                    PublicationCandidateModel.state == "READY",
                )
                .order_by(PublicationCandidateModel.priority.desc(), PublicationCandidateModel.id)
            ).all()
            scheduled: list[dict[str, object]] = []
            for candidate in candidates:
                if len(existing) + len(scheduled) >= plan.daily_limit:
                    break
                if not self._is_currently_editorial_pass(candidate.content_key):
                    continue
                if not source_is_current(self._session, candidate.content_key):
                    continue
                if not candidate_technical_allowed(self._session, candidate):
                    continue
                if not self._review_is_current(candidate):
                    continue
                slot_index = next(
                    (
                        index
                        for index, slot in enumerate(available_slots)
                        if slot >= _utc(candidate.eligible_at)
                    ),
                    None,
                )
                if slot_index is None:
                    continue
                scheduled_for = available_slots.pop(slot_index)
                try:
                    with self._session.begin_nested():
                        item = PlannedPublicationModel(
                            candidate_id=candidate.id,
                            output_channel_id=plan.output_channel_id,
                            scheduled_for=scheduled_for,
                            state="PLANNED",
                        )
                        self._session.add(item)
                        self._session.flush()
                    candidate.state = "SCHEDULED"
                    scheduled.append(_item_projection(item, candidate))
                except IntegrityError:
                    # A concurrent planner reserved the candidate/slot; it remains non-published.
                    continue
            self._session.commit()
            return sorted(existing + scheduled, key=lambda item: str(item["scheduled_for"]))
        except Exception:
            self._session.rollback()
            raise

    def _existing_for_day(
        self, plan: PublicationPlanModel, day: date, zone: ZoneInfo
    ) -> list[dict[str, object]]:
        starts_at = datetime.combine(day, time.min, zone).astimezone(UTC)
        ends_at = datetime.combine(day, time.max, zone).astimezone(UTC)
        rows = self._session.execute(
            select(PlannedPublicationModel, PublicationCandidateModel)
            .join(
                PublicationCandidateModel,
                PlannedPublicationModel.candidate_id == PublicationCandidateModel.id,
            )
            .where(
                PlannedPublicationModel.output_channel_id == plan.output_channel_id,
                or_(
                    PlannedPublicationModel.state.in_(("PLANNED", "PUBLISHED")),
                    select(PublicationJobModel.id)
                    .where(
                        PublicationJobModel.planned_id == PlannedPublicationModel.id,
                        PublicationJobModel.state.in_(
                            ("SENDING", "NEEDS_RECONCILIATION", "SUCCEEDED")
                        ),
                    )
                    .exists(),
                ),
                PlannedPublicationModel.scheduled_for >= starts_at,
                PlannedPublicationModel.scheduled_for <= ends_at,
            )
            .order_by(PlannedPublicationModel.scheduled_for)
        )
        return [_item_projection(item, candidate) for item, candidate in rows]

    def _reconcile_stale_reservations(
        self, plan: PublicationPlanModel, day: date, zone: ZoneInfo
    ) -> None:
        starts_at = datetime.combine(day, time.min, zone).astimezone(UTC)
        ends_at = datetime.combine(day, time.max, zone).astimezone(UTC)
        rows = self._session.execute(
            select(PlannedPublicationModel, PublicationCandidateModel)
            .join(
                PublicationCandidateModel,
                PlannedPublicationModel.candidate_id == PublicationCandidateModel.id,
            )
            .where(
                PlannedPublicationModel.output_channel_id == plan.output_channel_id,
                PlannedPublicationModel.state == "PLANNED",
                PlannedPublicationModel.scheduled_for >= starts_at,
                PlannedPublicationModel.scheduled_for <= ends_at,
            )
            .with_for_update()
        )
        for item, candidate in rows:
            remote_state = self._session.scalar(
                select(PublicationJobModel.state).where(PublicationJobModel.planned_id == item.id)
            )
            if remote_state in {"SENDING", "NEEDS_RECONCILIATION", "SUCCEEDED"}:
                # A cancelled/revoked reservation is not proof Telegram did not
                # publish it. Hold quota until exact delivery reconciliation.
                continue
            if not self._is_currently_editorial_pass(candidate.content_key):
                item.state = "BLOCKED_EDITORIAL"
                candidate.state = "BLOCKED_EDITORIAL"
            elif not source_is_current(self._session, candidate.content_key):
                item.state = "BLOCKED_SOURCE"
                candidate.state = "BLOCKED_SOURCE"
            elif not candidate_technical_allowed(self._session, candidate):
                item.state = "BLOCKED_TECHNICAL"
                candidate.state = "BLOCKED_TECHNICAL"
            elif not self._review_is_current(candidate):
                item.state = "BLOCKED_REVIEW"
                candidate.state = "BLOCKED_REVIEW"
        self._session.flush()

    def _review_is_current(self, candidate: PublicationCandidateModel) -> bool:
        output = self._session.scalar(
            select(RewriteOutputModel).where(
                RewriteOutputModel.content_key == candidate.content_key,
                RewriteOutputModel.output_channel_id == candidate.output_channel_id,
            )
        )
        # Preserve the no-rewrite domain prototype. Actual ingestion candidates
        # remain AWAITING_REWRITE until a draft has been explicitly approved.
        return output is None or approval_is_current(self._session, output)

    def _require_editorial_pass(self, content_key: str) -> None:
        if not self._is_currently_editorial_pass(content_key):
            raise CandidateBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")

    def _is_currently_editorial_pass(self, content_key: str) -> bool:
        decision = self._session.scalar(
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == content_key)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        return editorial_allows_rewrite(decision)
