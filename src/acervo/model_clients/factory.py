from acervo.core.errors import DecisionUnavailable
from acervo.core.settings import Settings
from acervo.model_clients.cache import DecisionCache
from acervo.model_clients.decider import Decider
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.model_clients.jev import JevDecider
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
        # `JEV_API_KEY=` left empty in .env reads as "", not None.
        if not (key := settings.jev_api_key.get_secret_value() if settings.jev_api_key else ""):
            raise DecisionUnavailable("DECIDER=jev needs JEV_API_KEY; set it, or use DECIDER=llm.")
        return JevDecider(settings.jev_url, settings.jev_model, key, _DECISION_CACHE)
    return LlmDecider(settings.llm_roles.decide, _DECISION_CACHE)


def build_writer(settings: Settings) -> Writer:
    if settings.decider == "fake":
        return FakeWriter()
    return LlmWriter(settings.llm_roles.model_dump())
