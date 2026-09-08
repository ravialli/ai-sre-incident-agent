from langchain.chat_models import init_chat_model

from app.config.settings import settings
from app.models.incident import IncidentAnalysis


def get_chat_model():
    kwargs = {}

    if (settings.llm_provider == "anthropic" and settings.anthropic_workspace_id):
        kwargs["default_headers"] = {"anthropic-workspace-id": settings.anthropic_workspace_id}

    return init_chat_model(model=settings.llm_model, model_provider=settings.llm_provider, **kwargs)


def get_incident_analysis_model():
    model = get_chat_model()

    structured_model = model.with_structured_output(IncidentAnalysis)

    return structured_model.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)