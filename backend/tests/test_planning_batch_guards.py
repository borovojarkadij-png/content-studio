"""A bounded planning snapshot cannot admit changed or late identities."""

from datetime import date

import pytest
from sqlalchemy import event, func, select
from test_planner_media_postgres import automatic_pair

from newsflow.persistence.models import (
    PlannedPublicationModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
)
from newsflow.services.publication_planning import PlanValidationError, PublicationPlanningService

DAY = date(2030, 1, 1)


@pytest.mark.parametrize("change", ["candidate-state", "draft-job", "source"])
def test_planning_revalidates_after_waiting_for_batch_locks(semantic_store, change):
    second, _ = automatic_pair(semantic_store)
    with semantic_store() as session:
        plan = PublicationPlanningService(session).configure_plan(1, "AUTOMATIC", 2, (540, 600))
    with semantic_store() as planning:
        fired = False

        @event.listens_for(planning, "do_orm_execute")
        def concurrent_change(execution):
            nonlocal fired
            statement = execution.statement
            if fired or getattr(statement, "_for_update_arg", None) is None:
                return
            if not any(
                item.get("entity") is RewriteJobModel for item in statement.column_descriptions
            ):
                return
            fired = True
            with semantic_store.begin() as writer:
                if change == "candidate-state":
                    writer.get(PublicationCandidateModel, second).state = "REJECTED_REVIEW"
                elif change == "draft-job":
                    output = writer.scalar(
                        select(RewriteOutputModel).where(
                            RewriteOutputModel.content_key == "synthetic:@semantic:2:revision:1"
                        )
                    )
                    replacement = RewriteJobModel(
                        content_key="synthetic-rebound-job",
                        output_channel_id=1,
                        idempotency_key="synthetic-rebound-job",
                        state="SUCCEEDED",
                    )
                    writer.add(replacement)
                    writer.flush()
                    output.rewrite_job_id = replacement.id
                else:
                    from newsflow.persistence.models import ContentRevisionModel

                    writer.add(
                        ContentRevisionModel(
                            incoming_post_id=2,
                            revision_number=2,
                            source_text="Новая редакция источника.",
                        )
                    )

        planned = PublicationPlanningService(planning).plan_day(plan["id"], DAY)
        assert fired
        assert [item["candidate_id"] for item in planned] == [1]


def test_candidate_arriving_after_batch_snapshot_waits_for_next_tick(semantic_store):
    second, _ = automatic_pair(semantic_store)
    with semantic_store.begin() as session:
        session.get(PublicationCandidateModel, second).state = "AWAITING_REWRITE"
    with semantic_store() as session:
        plan = PublicationPlanningService(session).configure_plan(1, "AUTOMATIC", 2, (540, 600))
    with semantic_store() as planning:
        fired = False

        @event.listens_for(planning, "do_orm_execute")
        def become_ready(execution):
            nonlocal fired
            statement = execution.statement
            if fired or getattr(statement, "_for_update_arg", None) is None:
                return
            if any(item.get("entity") is RewriteJobModel for item in statement.column_descriptions):
                fired = True
                with semantic_store.begin() as writer:
                    writer.get(PublicationCandidateModel, second).state = "READY"

        service = PublicationPlanningService(planning)
        assert [item["candidate_id"] for item in service.plan_day(plan["id"], DAY)] == [1]
        assert fired
        assert len(service.plan_day(plan["id"], DAY)) == 2


def test_over_capacity_rolls_back_without_partial_plan_or_candidate_changes(semantic_store):
    with semantic_store.begin() as session:
        session.add_all(
            [
                PublicationCandidateModel(
                    output_channel_id=1,
                    content_key=f"synthetic-overflow:{i}",
                    priority=0,
                    state="READY",
                )
                for i in range(1001)
            ]
        )
    with semantic_store() as session:
        service = PublicationPlanningService(session)
        plan = service.configure_plan(1, "AUTOMATIC", 2, (540, 600))
        with pytest.raises(PlanValidationError, match="capacity"):
            service.plan_day(plan["id"], DAY)
        assert session.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(PublicationCandidateModel)
                .where(PublicationCandidateModel.state == "READY")
            )
            == 1001
        )
