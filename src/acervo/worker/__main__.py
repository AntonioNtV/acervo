"""`python -m acervo.worker`: runs the digest worker and creates its hourly schedule when missing."""

import asyncio
import contextlib
import logging
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleSpec,
)
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from acervo.core.settings import get_settings
from acervo.db.session import create_engine, create_session_factory
from acervo.services.mailer import FakeMailer, Mailer
from acervo.services.smtp_mailer import SmtpMailer
from acervo.worker.activities import DigestActivities
from acervo.worker.workflows import DigestWorkflow

SCHEDULE_ID = "digest"


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address, namespace=settings.temporal_namespace, data_converter=pydantic_data_converter
    )
    action = ScheduleActionStartWorkflow(DigestWorkflow.run, id=SCHEDULE_ID, task_queue=settings.temporal_task_queue)
    # On the hour in UTC, so every time zone, :30 and :45 offsets included, passes 8:xx once a day.
    spec = ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))])
    with contextlib.suppress(ScheduleAlreadyRunningError):
        await client.create_schedule(SCHEDULE_ID, Schedule(action=action, spec=spec))
    mailer: Mailer
    if settings.smtp_host:
        mailer = SmtpMailer(settings)
    else:
        logging.getLogger(__name__).warning("SMTP_HOST is not set: emails are not sent.")
        mailer = FakeMailer()
    engine = create_engine(settings)
    activities = DigestActivities(create_session_factory(engine), mailer)
    try:
        await Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[DigestWorkflow],
            activities=[activities.due, activities.send],
        ).run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
