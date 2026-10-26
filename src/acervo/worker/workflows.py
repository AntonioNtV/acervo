import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from acervo.worker.activities import DigestActivities

TIMEOUT = timedelta(minutes=5)


@workflow.defn(name="digest")
class DigestWorkflow:
    """One hourly run: the accounts at 8:xx local, then one digest each."""

    @workflow.run
    async def run(self) -> None:
        now = workflow.now()
        due = await workflow.execute_activity_method(DigestActivities.due, now, start_to_close_timeout=TIMEOUT)
        await asyncio.gather(
            *(
                workflow.execute_activity_method(
                    DigestActivities.send, args=[account_id, now], start_to_close_timeout=TIMEOUT
                )
                for account_id in due
            )
        )
