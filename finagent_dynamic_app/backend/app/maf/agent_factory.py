"""Native Microsoft Agent Framework agent factory for financial research agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

import structlog

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient

from ..infra.settings import Settings

logger = structlog.get_logger(__name__)

_MODELS_WITHOUT_TEMPERATURE = {"chato1", "chat41mini", "chat4omini"}


@dataclass(slots=True)
class AgentDefinition:
    """Metadata describing a native MAF chat agent archetype."""

    type_name: str
    system_prompt: str
    description: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    defaults: Dict[str, Any] = field(default_factory=dict)
    azure_name: Optional[str] = None
    model_deployment_name: Optional[str] = None


class MAFAgentFactory:
    """Factory that provides configured `ChatAgent` instances for the app."""

    def __init__(
        self,
        settings: Settings,
        *,
        chat_client: Optional[AzureAIAgentClient] = None,
        chat_agent_cls: Type[ChatAgent] = ChatAgent,
    ) -> None:
        self._settings = settings
        self._chat_agent_cls = chat_agent_cls
        self._credential: Optional[DefaultAzureCredential] = None
        self._project_client: Optional[AIProjectClient] = None
        self._chat_client = chat_client or self._build_chat_client(settings)
        self._registry: Dict[str, AgentDefinition] = {}
        self._agent_clients: Dict[str, AzureAIAgentClient] = {}
        self._agent_ids: Dict[str, str] = {}
        self._agent_models: Dict[str, str] = {}
        self._known_remote_agents: Dict[str, Any] = {}
        self._prepared = False
        self._register_default_agents()
        logger.info("Financial MAF agent factory initialised", available=list(self._registry))

    def _build_chat_client(self, settings: Settings) -> AzureAIAgentClient:
        """Create an Azure AI agent client for Microsoft Agent Framework usage."""
        if not settings.azure_ai_project_endpoint or not settings.azure_ai_model_deployment_name:
            raise ValueError(
                "Azure AI configuration missing. Set AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME."
            )

        try:
            self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            
            # Create AIProjectClient for direct agent management
            self._project_client = AIProjectClient(
                endpoint=settings.azure_ai_project_endpoint,
                credential=self._credential,
            )
            
            # Create AzureAIAgentClient with the project_client
            client = AzureAIAgentClient(
                project_client=self._project_client,
                model_deployment_name=settings.azure_ai_model_deployment_name,
                async_credential=self._credential,
            )
            logger.debug("Azure AI agent client created for financial MAF agents")
            return client
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to build Azure AI agent client", error=str(exc))
            raise

    def _register_default_agents(self) -> None:
        """Register the core agent archetypes used across the financial workflows."""
        self.register_agent_type(
            AgentDefinition(
                type_name="planner",
                description="Leads research planning and orchestrates agent collaboration",
                system_prompt=(
                    "You are the lead financial research planner. Analyse objectives, determine"
                    " the required research tracks (company profile, SEC filings, earnings,"
                    " fundamentals, technicals, forecasts, summaries, reports) and produce"
                    " an execution plan tailored to the user's goals."
                ),
                tags=("planning", "financial", "strategy"),
                azure_name="financial_planner",
                model_deployment_name="chato1",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="company",
                description="Provides company intelligence using finance data providers",
                system_prompt=(
                    "You are a company intelligence specialist using market data, profile"
                    " information, and news to describe the business, key metrics, and"
                    " current catalysts."
                ),
                tags=("company", "profile"),
                defaults={"temperature": 0.3},
                azure_name="financial_company_agent",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="sec",
                description="Analyses SEC filings and regulatory documents",
                system_prompt=(
                    "You are an SEC filings expert. Extract material information, risk factors,"
                    " forward-looking statements, and compliance issues from regulatory filings."
                ),
                tags=("sec", "regulation"),
                azure_name="financial_sec_agent",
                model_deployment_name="chat41mini",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="earnings",
                description="Reviews earnings transcripts and quarterly performance",
                system_prompt=(
                    "You specialise in earnings events. Analyse transcripts, guidance,"
                    " revenue drivers, and management commentary to surface key takeaways."
                ),
                tags=("earnings", "transcripts"),
                defaults={"temperature": 0.25},
                azure_name="financial_earnings_agent",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="fundamentals",
                description="Performs fundamental financial analysis",
                system_prompt=(
                    "You are a fundamental analyst who evaluates financial statements,"
                    " ratio trends, liquidity, profitability, and valuation context."
                ),
                tags=("fundamentals", "valuation"),
                defaults={"temperature": 0.2},
                azure_name="financial_fundamentals_agent",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="technicals",
                description="Conducts technical price analysis",
                system_prompt=(
                    "You focus on technical analysis using price action, indicators,"
                    " chart patterns, and momentum signals to describe trends and setups."
                ),
                tags=("technicals", "charts"),
                defaults={"temperature": 0.25},
                azure_name="financial_technicals_agent",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="forecaster",
                description="Produces forecasts and scenario analysis",
                system_prompt=(
                    "You create forward-looking forecasts by combining fundamental, technical,"
                    " and sentiment signals. Provide base, bull, and bear scenarios when helpful."
                ),
                tags=("forecasting", "scenarios"),
                azure_name="financial_forecaster_agent",
                model_deployment_name="chat4omini",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="summarizer",
                description="Synthesises research into concise narratives",
                system_prompt=(
                    "You summarise financial research for specific audiences, balancing context,"
                    " opportunities, risks, and recommendations. Tailor tone to the requested persona."
                ),
                tags=("summary", "persona"),
                defaults={"temperature": 0.2},
                azure_name="financial_summarizer_agent",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="report",
                description="Creates structured research reports",
                system_prompt=(
                    "You compile multi-agent findings into structured reports with sections such"
                    " as investment thesis, financial highlights, risk considerations, and next steps."
                ),
                tags=("report", "synthesis"),
                defaults={"temperature": 0.2},
                azure_name="financial_report_agent",
            )
        )

    def register_agent_type(self, definition: AgentDefinition) -> None:
        """Register or update an agent archetype."""
        self._registry[definition.type_name] = definition
        logger.debug("Registered financial agent type", type=definition.type_name)

    def list_agent_types(self) -> list[AgentDefinition]:
        """Return the registered agent definitions."""
        return list(self._registry.values())

    def get_definition(self, agent_type: str) -> AgentDefinition:
        """Retrieve an agent definition by type."""
        if agent_type not in self._registry:
            raise KeyError(f"Unknown agent type: {agent_type}")
        return self._registry[agent_type]

    def create_chat_agent(
        self,
        agent_type: str,
        *,
        name: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> ChatAgent:
        """Instantiate a chat agent configured for the specified archetype."""
        if not self._prepared:
            raise RuntimeError("MAFAgentFactory.prepare() must be awaited before creating chat agents.")
        definition = self.get_definition(agent_type)
        config = {**definition.defaults}
        if overrides:
            config.update(overrides)

        agent_name = name or definition.azure_name or agent_type
        logger.info(
            "Creating financial MAF chat agent",
            agent_type=agent_type,
            agent_name=agent_name,
        )
        chat_client = self._agent_clients.get(agent_type)
        if not chat_client:
            raise KeyError(f"Azure AI chat client not initialised for agent type '{agent_type}'")

        return self._chat_agent_cls(
            name=agent_name,
            chat_client=chat_client,
            id=self._agent_ids.get(agent_type),
            instructions=definition.system_prompt,
            **config,
        )

    @property
    def chat_client(self) -> AzureAIAgentClient:
        """Expose the underlying chat client for advanced consumers."""
        return self._chat_client

    def get_agent_client(self, agent_type: str) -> AzureAIAgentClient:
        """Retrieve the dedicated Azure AI client for a specific agent type."""
        if not self._prepared:
            raise RuntimeError("MAFAgentFactory.prepare() must be awaited before accessing agent clients.")
        if agent_type not in self._agent_clients:
            raise KeyError(f"Unknown agent type '{agent_type}'")
        return self._agent_clients[agent_type]

    def get_agent_model(self, agent_type: str) -> str:
        """Return the model deployment name associated with an agent type."""
        if not self._prepared:
            raise RuntimeError("MAFAgentFactory.prepare() must be awaited before accessing agent models.")
        if agent_type not in self._agent_models:
            raise KeyError(f"Unknown agent type '{agent_type}'")
        return self._agent_models[agent_type]

    async def prepare(self) -> None:
        """Ensure Azure AI agents exist and observability is configured."""
        if self._prepared:
            return

        await self._configure_observability()
        await self._synchronise_remote_agents()
        self._prepared = True

    async def _configure_observability(self) -> None:
        """Enable Azure AI observability based on settings."""
        if not self._settings.observability_enabled:
            logger.debug("Observability disabled in settings")
            return

        try:
            configured = False
            enable_sensitive = self._settings.observability_enable_sensitive_data
            if self._settings.observability_otlp_endpoint or self._settings.applicationinsights_connection_string:
                from agent_framework.observability import setup_observability

                setup_observability(
                    otlp_endpoint=self._settings.observability_otlp_endpoint,
                    applicationinsights_connection_string=self._settings.applicationinsights_connection_string,
                    enable_sensitive_data=enable_sensitive,
                )
                configured = True
                logger.info(
                    "Observability configured via settings",
                    has_otlp=bool(self._settings.observability_otlp_endpoint),
                    has_appinsights=bool(self._settings.applicationinsights_connection_string),
                    sensitive_data=enable_sensitive,
                )

            if not configured:
                await self._chat_client.setup_azure_ai_observability(enable_sensitive_data=enable_sensitive)
                configured = True
                logger.info(
                    "Azure AI observability enabled for project",
                    sensitive_data=enable_sensitive,
                )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to configure observability", error=str(exc))

    async def _synchronise_remote_agents(self) -> None:
        """Create or update Azure AI agents for each registered definition."""
        for definition in self.list_agent_types():
            base_model_name = self._settings.DEFAULT_MODEL_DEPLOYMENT
            agent_model = definition.model_deployment_name or base_model_name
            if not agent_model:
                raise ValueError(
                    f"No model deployment configured for agent '{definition.type_name}'. Set a default deployment"
                    " or provide a model_deployment_name override."
                )

            azure_name = self._resolve_azure_name(definition)
            agent = await self._get_existing_agent(azure_name)
            temperature = definition.defaults.get("temperature")
            if temperature is not None and agent_model in _MODELS_WITHOUT_TEMPERATURE:
                logger.info(
                    "Skipping temperature for agent model without support",
                    agent_type=definition.type_name,
                    model=agent_model,
                )
                temperature = None

            if agent is None:
                create_kwargs = dict(
                    model=agent_model,
                    name=azure_name,
                    description=definition.description,
                    instructions=definition.system_prompt,
                )
                if temperature is not None:
                    create_kwargs["temperature"] = temperature

                created = await self._project_client.agents.create_agent(**create_kwargs)
                agent_id = str(created.id)
                self._known_remote_agents[azure_name] = created
                logger.info("Created Azure AI agent", agent_type=definition.type_name, agent_name=azure_name)
            else:
                update_kwargs = dict(
                    agent_id=str(agent.id),
                    model=agent_model,
                    name=azure_name,
                    description=definition.description,
                    instructions=definition.system_prompt,
                )
                if temperature is not None:
                    update_kwargs["temperature"] = temperature

                updated = await self._project_client.agents.update_agent(**update_kwargs)
                agent_id = str(updated.id if hasattr(updated, "id") else agent.id)
                self._known_remote_agents[azure_name] = updated
                logger.info("Updated Azure AI agent", agent_type=definition.type_name, agent_name=azure_name)

            self._agent_ids[definition.type_name] = agent_id
            self._agent_models[definition.type_name] = agent_model
            self._agent_clients[definition.type_name] = AzureAIAgentClient(
                project_client=self._project_client,
                agent_id=agent_id,
                agent_name=azure_name,
                model_deployment_name=agent_model,
                async_credential=self._credential,
            )

        planner_id = self._agent_ids.get("planner")
        if planner_id:
            planner_definition = self.get_definition("planner")
            self._chat_client.agent_id = planner_id
            self._chat_client.agent_name = self._resolve_azure_name(planner_definition)
            planner_model = self._agent_models.get("planner")
            if planner_model and hasattr(self._chat_client, "model_deployment_name"):
                self._chat_client.model_deployment_name = planner_model
            # Ensure shared client never deletes the planner agent on close
            if hasattr(self._chat_client, "_should_delete_agent"):
                self._chat_client._should_delete_agent = False

    async def _get_existing_agent(self, azure_name: str) -> Any:
        """Lookup an existing Azure AI agent by name."""
        if azure_name in self._known_remote_agents:
            return self._known_remote_agents[azure_name]

        async for agent in self._project_client.agents.list_agents():
            if agent.name == azure_name:
                self._known_remote_agents[azure_name] = agent
                return agent
        return None

    def _resolve_azure_name(self, definition: AgentDefinition) -> str:
        """Compute a stable Azure AI agent name for a definition."""
        if definition.azure_name:
            return definition.azure_name
        return f"financial_{definition.type_name}_agent"

    async def close(self) -> None:
        """Release underlying Azure resources."""
        try:
            for client in self._agent_clients.values():
                await client.close()
            if self._chat_client:
                await self._chat_client.close()
            if self._project_client:
                await self._project_client.close()
        finally:
            if self._credential:
                await self._credential.close()
