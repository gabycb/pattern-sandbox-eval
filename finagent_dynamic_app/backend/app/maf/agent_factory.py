"""Native Microsoft Agent Framework agent factory for financial research agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

import structlog

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIClient
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
        chat_client: Optional[AzureAIClient] = None,
        chat_agent_cls: Type[ChatAgent] = ChatAgent,
    ) -> None:
        self._settings = settings
        self._chat_agent_cls = chat_agent_cls
        self._credential: Optional[DefaultAzureCredential] = None
        self._project_client: Optional[AIProjectClient] = None
        self._chat_client = chat_client or self._build_chat_client(settings)
        self._registry: Dict[str, AgentDefinition] = {}
        self._agent_clients: Dict[str, Any] = {}  # Stores AzureAIClient instances for v2 agents
        self._agent_ids: Dict[str, str] = {}
        self._agent_models: Dict[str, str] = {}
        self._agent_versions: Dict[str, str] = {}
        self._known_remote_agents: Dict[str, Any] = {}
        self._prepared = False
        self._register_default_agents()
        logger.info("Financial MAF agent factory initialised", available=list(self._registry))

    def _build_chat_client(self, settings: Settings) -> AzureAIClient:
        """Create an Azure AI agent client for Microsoft Agent Framework usage."""
        if not settings.azure_ai_project_endpoint or not settings.azure_ai_model_deployment_name:
            raise ValueError(
                "Azure AI configuration missing. Set AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME."
            )

        try:
            # Use synchronous ClientSecretCredential to avoid Windows aiodns issues
            # The sync credential works with async clients via internal wrapping
            if settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret:
                from azure.identity import ClientSecretCredential
                self._credential = ClientSecretCredential(
                    tenant_id=settings.azure_tenant_id,
                    client_id=settings.azure_client_id,
                    client_secret=settings.azure_client_secret
                )
                logger.debug("Using synchronous ClientSecretCredential with ENTRA_AGENT_CLIENT_ID")
            else:
                self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
                logger.debug("Using DefaultAzureCredential")
            
            # Create AIProjectClient for direct agent management
            self._project_client = AIProjectClient(
                endpoint=settings.azure_ai_project_endpoint,
                credential=self._credential,
            )
            
            # Create V2 AzureAIClient with the project_client
            # This is used as a fallback/shared client; individual agents get their own V2 clients
            client = AzureAIClient(
                project_client=self._project_client,
                model_deployment_name=settings.azure_ai_model_deployment_name,
            )
            logger.info(
                "[AGENT_CREATION_DEBUG] Created shared AzureAIClient (V2)",
                model=settings.azure_ai_model_deployment_name,
                has_agent_name=hasattr(client, 'agent_name') and client.agent_name is not None
            )
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
                azure_name="financial-planner-agent",
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
                azure_name="financial-company-agent",
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
                azure_name="financial-sec-agent",
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
                azure_name="financial-earnings-agent",
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
                azure_name="financial-fundamentals-agent",
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
                tags=("technicals", "charting"),
                defaults={"temperature": 0.2},
                azure_name="financial-technicals-agent",
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
                defaults={"temperature": 0.5},
                azure_name="financial-forecaster-agent",
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
                azure_name="financial-summarizer-agent",
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
                tags=("reporting", "synthesis"),
                defaults={"temperature": 0.4},
                azure_name="financial-report-agent",
            )
        )

        self.register_agent_type(
            AgentDefinition(
                type_name="ticker_extraction",
                description="Extracts U.S. stock ticker symbols from text",
                system_prompt=(
                    "You are an expert financial analyst specializing in identifying stock ticker symbols. "
                    "Your task is to extract the U.S. stock ticker symbol from user queries about companies or stocks.\n\n"
                    "Key Rules:\n"
                    "1. Return ONLY the ticker symbol in uppercase (e.g., AAPL, TSLA, MSFT)\n"
                    "2. If the text mentions a company name, return its corresponding ticker symbol\n"
                    "3. If the text already contains a ticker symbol, return that ticker\n"
                    "4. If NO company or ticker is mentioned, return exactly 'NONE'\n"
                    "5. Never include explanations, just the ticker or 'NONE'\n\n"
                    "Examples:\n"
                    "- 'Tesla' → TSLA\n"
                    "- 'Apple Inc.' → AAPL\n"
                    "- 'Microsoft Corporation' → MSFT\n"
                    "- 'NVDA stock analysis' → NVDA\n"
                    "- 'Analyze GOOGL performance' → GOOGL\n"
                    "- 'Amazon forecast' → AMZN\n"
                    "- 'Meta Platforms' → META\n"
                    "- 'Alphabet' → GOOGL\n"
                    "- 'JPMorgan Chase' → JPM\n"
                    "- 'What is the weather?' → NONE"
                ),
                tags=("extraction", "ticker"),
                defaults={"temperature": 0.0},
                azure_name="financial-ticker-extraction-agent",
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

        logger.info(
            "[AGENT_CREATION_DEBUG] Creating ChatAgent instance",
            agent_type=agent_type,
            agent_name=agent_name,
            config_keys=list(config.keys()),
            client_has_agent_id=hasattr(chat_client, 'agent_id') and chat_client.agent_id is not None,
            client_has_agent_name=hasattr(chat_client, 'agent_name') and chat_client.agent_name is not None,
            client_agent_id=getattr(chat_client, 'agent_id', None),
            client_agent_name=getattr(chat_client, 'agent_name', None)
        )

        # Create ChatAgent with V2 client (instructions already in V2 agent definition)
        chat_agent = self._chat_agent_cls(
            name=agent_name,
            chat_client=chat_client,
            **config,
        )
        
        logger.info(
            "[AGENT_CREATION_DEBUG] ChatAgent instance created",
            agent_type=agent_type,
            chat_agent_name=chat_agent.name,
            chat_agent_has_id=hasattr(chat_agent, 'id') and chat_agent.id is not None,
            chat_agent_id=getattr(chat_agent, 'id', None)
        )
        
        return chat_agent

    @property
    def chat_client(self) -> AzureAIClient:
        """Expose the underlying chat client for advanced consumers."""
        return self._chat_client

    def get_agent_client(self, agent_type: str) -> AzureAIClient:
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

            if not configured and hasattr(self._chat_client, 'setup_azure_ai_observability'):
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

            # Create or update agent version (v2 API uses versioned agents)
            from azure.ai.projects.models import PromptAgentDefinition
            
            create_params = {
                "model": agent_model,
                "instructions": definition.system_prompt
            }
            if temperature is not None:
                create_params["temperature"] = temperature
            
            agent_def = PromptAgentDefinition(**create_params)
            
            # Always create a new version (v2 agents are versioned)
            agent_version_obj = await self._project_client.agents.create_version(
                agent_name=azure_name,
                definition=agent_def
            )
            
            # Extract version info
            agent_version = agent_version_obj.version
            agent_id = agent_version_obj.id  # Format: "agent-name:version"
            
            self._known_remote_agents[azure_name] = agent_version_obj
            self._agent_ids[definition.type_name] = str(agent_id)
            self._agent_models[definition.type_name] = agent_model
            self._agent_versions[definition.type_name] = agent_version
            
            if agent is None:
                logger.info("Created Azure AI agent version (v2)", agent_type=definition.type_name, agent_name=azure_name, version=agent_version)
            else:
                logger.info("Created new version for Azure AI agent (v2)", agent_type=definition.type_name, agent_name=azure_name, version=agent_version)
            
            # Use V2 AzureAIClient to reference pre-created V2 agents by name and version
            agent_client = AzureAIClient(
                project_client=self._project_client,
                agent_name=azure_name,
                agent_version=agent_version,
            )
            logger.info(
                "[AGENT_CREATION_DEBUG] Created agent-specific AzureAIClient (V2)",
                agent_type=definition.type_name,
                azure_name=azure_name,
                agent_id=agent_id,
                agent_version=agent_version,
                model=agent_model,
                has_client_agent_name=hasattr(agent_client, 'agent_name') and agent_client.agent_name is not None,
                client_agent_name=getattr(agent_client, 'agent_name', None)
            )
            self._agent_clients[definition.type_name] = agent_client

        # Don't set agent_id or agent_name on the chat client - both force v1 Assistants API
        # Azure AI Projects SDK 2.0 uses v2 Agents API (prompt templates managed separately)
        planner_id = self._agent_ids.get("planner")
        if planner_id:
            planner_definition = self.get_definition("planner")
            # Only set model, not agent_id or agent_name
            planner_model = self._agent_models.get("planner")
            if planner_model and hasattr(self._chat_client, "model_deployment_name"):
                self._chat_client.model_deployment_name = planner_model
            # Ensure shared client never deletes any agent on close
            if hasattr(self._chat_client, "_should_delete_agent"):
                self._chat_client._should_delete_agent = False
            
            logger.info(
                "[AGENT_CREATION_DEBUG] Configured shared chat_client for planner",
                planner_id=planner_id,
                agent_name=self._chat_client.agent_name,
                model=planner_model,
                has_agent_id=hasattr(self._chat_client, 'agent_id') and self._chat_client.agent_id is not None,
                client_agent_id=getattr(self._chat_client, 'agent_id', None)
            )

    async def _get_existing_agent(self, azure_name: str) -> Any:
        """Lookup an existing Azure AI agent by name."""
        if azure_name in self._known_remote_agents:
            return self._known_remote_agents[azure_name]

        # In Azure AI Projects SDK >=2.0.0b1, list_agents() was renamed to list()
        async for agent in self._project_client.agents.list():
            if agent.name == azure_name:
                # Debug: dump all agent properties as dictionary
                agent_dict = agent.as_dict() if hasattr(agent, 'as_dict') else {}
                logger.debug(f"Found existing agent dict: {agent_dict}")
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
