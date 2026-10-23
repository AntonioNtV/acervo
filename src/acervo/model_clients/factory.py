from acervo.core.errors import DecisionUnavailable
from acervo.core.settings import Settings
from acervo.model_clients.cache import DecisionCache
from acervo.model_clients.decider import Decider
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.model_clients.llm_decider import LlmDecider
from acervo.model_clients.llm_writer import LlmWriter
from acervo.model_clients.writer import Writer

# One cache for the process, so a state already decided is never sent again.
_DECISION_CACHE = DecisionCache()


def build_decider(settings: Settings) -> Decider:
    """The decider `settings.decider` names; the worker builds it, since the pipeline runs there."""
    if settings.decider == "fake":
        return FakeDecider()
    if settings.decider == "jev":
        raise DecisionUnavailable("Jev is not configured: its client is written once its docs or key are given.")
    return LlmDecider(settings.llm_roles.decide, _DECISION_CACHE)


def build_writer(settings: Settings) -> Writer:
    if settings.decider == "fake":
        return FakeWriter()
    return LlmWriter(settings.llm_roles.model_dump())
