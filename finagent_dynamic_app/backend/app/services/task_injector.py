"""
Task Injection Module

Handles intelligent task injection into existing plans with:
- Duplicate detection
- Capability validation
- Smart positioning (beginning, middle, end)
- Dependency resolution
"""

import re
import uuid
import structlog
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential
from agent_framework import ChatMessage, Role

from app.models.task_models import Step, StepStatus, AgentType
from app.infra.settings import Settings

logger = structlog.get_logger(__name__)

# Initialize settings
settings = Settings()


class TaskInjector:
    """
    Intelligent task injection service.
    
    Analyzes user requests and determines:
    1. If task already exists (duplicate)
    2. If we have capabilities (agents/tools)
    3. Where to insert (beginning, middle, end)
    4. What dependencies to set
    """
    
    def __init__(self):
        logger.info("TaskInjector: Initializing LLM client")
        logger.info(
            "TaskInjector: Settings - Azure AI project configured",
            has_project_endpoint=bool(settings.azure_ai_project_endpoint),
            model=settings.azure_ai_model_deployment_name,
        )

        if not settings.azure_ai_project_endpoint or not settings.azure_ai_model_deployment_name:
            raise ValueError("TaskInjector requires Azure AI configuration. Set AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME")

        self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        self.llm_client = AzureAIAgentClient(
            project_endpoint=settings.azure_ai_project_endpoint,
            model_deployment_name=settings.azure_ai_model_deployment_name,
            async_credential=self._credential,
        )
        self._agent_name = "financial_task_injector"
        self._prepared = False
        logger.info("TaskInjector: Azure AI agent client created", client_type=type(self.llm_client).__name__)
        
        # Define available agents and their capabilities
        self.agent_capabilities = {
            "Company_Agent": {
                "tools": ["get_yahoo_finance_news", "get_recommendations", "get_stock_info", "get_historical_prices"],
                "description": "Company information, news, recommendations, stock data"
            },
            "Forecaster_Agent": {
                "tools": ["predict_stock_movement", "analyze_positive_developments", "analyze_potential_concerns", "technical_analysis"],
                "description": "Stock predictions, forecasts, technical analysis"
            },
            "Summarizer_Agent": {
                "tools": ["generate_sentiment_summary", "summarize_information", "create_news_summary", "synthesize_findings"],
                "description": "Sentiment analysis, summaries, synthesis"
            },
            "Report_Agent": {
                "tools": ["document_generation", "data_aggregation", "pattern_analysis"],
                "description": "Comprehensive reports, research briefs"
            },
            "SEC_Agent": {
                "tools": ["sec_filings", "form_10k", "form_10q"],
                "description": "SEC filings and regulatory documents"
            },
            "EarningCall_Agent": {
                "tools": ["earnings_data", "transcripts", "earnings_calendar"],
                "description": "Earnings reports and call transcripts"
            },
            "Fundamentals_Agent": {
                "tools": ["financial_ratios", "income_statement", "balance_sheet"],
                "description": "Fundamental financial analysis"
            },
            "Technicals_Agent": {
                "tools": ["price_data", "indicators", "chart_patterns"],
                "description": "Technical analysis and chart patterns"
            }
        }
    
    async def analyze_injection_request(
        self,
        task_request: str,
        objective: str,
        current_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze the task injection request using LLM.
        
        Args:
            task_request: User's request to add a task
            objective: Original plan objective
            current_steps: List of current steps in the plan
            
        Returns:
            Analysis result with action, message, position, etc.
        """
        logger.info("TaskInjector: Starting analysis", task_request=task_request, step_count=len(current_steps))
        
        # Build the analysis prompt
        logger.info("TaskInjector: Building analysis prompt")
        analysis_prompt = self._build_analysis_prompt(task_request, objective, current_steps)
        logger.info("TaskInjector: Prompt built", prompt_length=len(analysis_prompt))
        
        # Call LLM for analysis
        logger.info("TaskInjector: Preparing LLM messages")
        messages = [
            ChatMessage(role=Role.SYSTEM, text="You are a task planning assistant. Analyze user requests for adding tasks to existing plans."),
            ChatMessage(role=Role.USER, text=analysis_prompt)
        ]
        logger.info("TaskInjector: Messages prepared, calling LLM")
        
        try:
            await self._ensure_agent_ready()
            logger.info("TaskInjector: Calling LLM client get_response")
            response = await self.llm_client.get_response(
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            logger.info("TaskInjector: LLM response received", response_type=type(response).__name__)
            
            analysis_text = response.text
            logger.info("LLM analysis completed", analysis_length=len(analysis_text))
            
            # Parse the analysis
            logger.info("TaskInjector: Parsing LLM response")
            result = self._parse_analysis(analysis_text, current_steps)
            logger.info("TaskInjector: Parse complete", result_type=type(result).__name__, action=result.get('action'))
            return result
            
        except Exception as e:
            logger.error("Error in LLM analysis", error=str(e), exc_info=True)
            return {
                "action": "unsupported",
                "message": f"Error analyzing request: {str(e)}",
                "success": False
            }

    async def close(self) -> None:
        """Release Azure credentials used by the injector."""
        try:
            if self.llm_client:
                await self.llm_client.close()
        finally:
            if self._credential:
                await self._credential.close()

    async def _ensure_agent_ready(self) -> None:
        """Ensure the Azure AI agent exists and client targets it."""
        if self._prepared:
            return

        project_client = self.llm_client.project_client

        existing_agent = None
        async for agent in project_client.agents.list_agents():
            if getattr(agent, "name", None) == self._agent_name:
                existing_agent = agent
                break

        if existing_agent is None:
            logger.info("TaskInjector: Creating Azure AI agent", agent_name=self._agent_name)
            description = "Analyzes plan injection requests for the financial research application"
            instructions = (
                "You analyze user task injection requests and output structured analysis including "
                "the action to take, reasoning, agents involved, and dependencies."
            )
            created = await project_client.agents.create_agent(
                name=self._agent_name,
                model=settings.azure_ai_model_deployment_name,
                description=description,
                instructions=instructions,
            )
            target_agent = created
        else:
            logger.info("TaskInjector: Reusing existing Azure AI agent", agent_name=self._agent_name)
            target_agent = existing_agent

        self.llm_client.agent_id = str(target_agent.id)
        self.llm_client.agent_name = target_agent.name
        if getattr(self.llm_client, "model_deployment_name", None) is not None:
            self.llm_client.model_deployment_name = settings.azure_ai_model_deployment_name
        if hasattr(self.llm_client, "_should_delete_agent"):
            self.llm_client._should_delete_agent = False

        self._prepared = True
    
    def _build_analysis_prompt(
        self,
        task_request: str,
        objective: str,
        current_steps: List[Dict[str, Any]]
    ) -> str:
        """Build the LLM prompt for task analysis."""
        # Format current steps
        steps_text = "\n".join([
            f"Step {step['order']}: {step['action']} (Agent: {step['agent']}, Status: {step['status']})"
            for step in sorted(current_steps, key=lambda x: x['order'])
        ])
        
        # Format available capabilities
        capabilities_text = "\n".join([
            f"- {agent}: {info['description']} (Tools: {', '.join(info['tools'])})"
            for agent, info in self.agent_capabilities.items()
        ])
        
        return f"""
OBJECTIVE: {objective}

CURRENT PLAN:
{steps_text}

AVAILABLE CAPABILITIES:
{capabilities_text}

USER REQUEST: "{task_request}"

ANALYSIS TASK:
Analyze if the user's request can be added to the plan. Provide your analysis in this EXACT format:

ACTION: [one of: DUPLICATE, UNSUPPORTED, ADD_BEGINNING, ADD_MIDDLE, ADD_END, CLARIFICATION]

REASONING: [Your reasoning for the action]

NEW_TASK: [If ACTION is ADD_*, describe the exact task to add]

AGENT: [If ACTION is ADD_*, specify which agent should handle it]

FUNCTION: [If ACTION is ADD_*, specify which tool/function to use]

INSERT_AFTER: [If ACTION is ADD_MIDDLE, specify the step number to insert after]

DEPENDENCIES: [If ACTION is ADD_*, list step numbers this task depends on, comma-separated, or "none"]

MESSAGE: [User-friendly message explaining the action]

RULES:
1. If the request is already covered in current steps, use ACTION: DUPLICATE
2. If we don't have the agent/tool for it, use ACTION: UNSUPPORTED
3. If it's a data gathering task, use ACTION: ADD_BEGINNING
4. If it's an analysis/synthesis task that needs previous data, use ACTION: ADD_MIDDLE or ADD_END
5. If request is unclear, use ACTION: CLARIFICATION

EXAMPLES:
- "get latest news" when news step exists → ACTION: DUPLICATE
- "execute a trade" when no trading agent → ACTION: UNSUPPORTED  
- "add stock prediction" when news exists → ACTION: ADD_END (depends on news)
- "get analyst recommendations" when no such step → ACTION: ADD_BEGINNING (data gathering)
"""
    
    def _parse_analysis(self, analysis_text: str, current_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse the LLM analysis response."""
        lines = analysis_text.strip().split('\n')
        result: Dict[str, Any] = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().upper()
                value = value.strip()
                
                if key == 'ACTION':
                    placement = value.lower()
                    result['placement'] = placement
                    result['action'] = placement.replace('add_', '')
                elif key == 'REASONING':
                    result['reasoning'] = value
                elif key == 'NEW_TASK':
                    result['new_task'] = value
                elif key == 'AGENT':
                    result['agent'] = value
                elif key == 'FUNCTION':
                    result['function'] = value
                elif key == 'INSERT_AFTER':
                    try:
                        result['insert_after'] = int(value) if value.lower() != 'none' else None
                    except:
                        result['insert_after'] = None
                elif key == 'DEPENDENCIES':
                    if value.lower() == 'none':
                        result['dependencies'] = []
                    else:
                        try:
                            result['dependencies'] = [int(d.strip()) for d in value.split(',')]
                        except:
                            result['dependencies'] = []
                elif key == 'MESSAGE':
                    result['message'] = value
        
        # Map action to success/failure
        action = result.get('action', 'unsupported')
        if action in ['beginning', 'middle', 'end']:
            result['success'] = True
            result['action'] = 'added'
            result['placement'] = result.get('placement')
        elif action == 'duplicate':
            result['success'] = False
            result['message'] = result.get('message', 'This task is already in your plan.')
        elif action == 'unsupported':
            result['success'] = False
            result['message'] = result.get('message', 'This capability is not currently supported.')
        elif action == 'clarification':
            result['success'] = False
            result['action'] = 'clarification_needed'
            result['message'] = result.get('message', 'Could you provide more details about what you want?')
        
        logger.info("Parsed analysis", action=result.get('action'), success=result.get('success'))
        return result
    
    def create_new_step(
        self,
        analysis: Dict[str, Any],
        current_steps: List[Step],
        plan_id: str,
        session_id: str,
        user_id: str
    ) -> Tuple[List[Step], int]:
        """Create one or more new steps based on analysis output.

        Returns a tuple containing the list of new steps (ordered as inserted)
        and the position at which the first step should be inserted.
        """
        insert_position = self._determine_insert_position(analysis, current_steps)
        
        # Map dependencies from step numbers to step IDs
        dependency_ids = self._map_dependencies(analysis, current_steps)

        agents = self._normalize_agents(analysis.get('agent')) or ['Generic_Agent']
        tasks = self._normalize_tasks(analysis.get('new_task'), len(agents))
        functions = self._normalize_functions(analysis.get('function'), len(agents))

        new_steps: List[Step] = []
        previous_step_id: Optional[str] = None

        for index, agent_name in enumerate(agents):
            resolved_agent = self._resolve_agent(agent_name)
            step_dependencies = list(dependency_ids)
            if index > 0 and previous_step_id:
                step_dependencies.append(previous_step_id)

            step = Step(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                session_id=session_id,
                user_id=user_id,
                order=insert_position + index,
                action=tasks[index] if index < len(tasks) else tasks[-1],
                agent=resolved_agent,
                status=StepStatus.PLANNED,
                dependencies=step_dependencies,
                tools=[functions[index]] if functions[index] else [],
                manually_injected=True,
                timestamp=datetime.utcnow(),
                data_type="step",
            )

            logger.info(
                "Created new step via injection",
                step_id=step.id,
                order=step.order,
                agent=step.agent.value,
                dependencies=len(step_dependencies),
                manually_injected=True,
            )

            new_steps.append(step)
            previous_step_id = step.id

        return new_steps, insert_position

    def _determine_insert_position(self, analysis: Dict[str, Any], current_steps: List[Step]) -> int:
        if analysis.get('insert_after') is not None:
            return analysis['insert_after'] + 1

        placement = (analysis.get('placement') or '').lower()
        if 'beginning' in placement:
            return 1

        if 'middle' in placement:
            midpoint = max(1, len(current_steps) // 2)
            return midpoint + 1

        if 'end' in placement:
            return len(current_steps) + 1

        if analysis.get('action') == 'added' and not current_steps:
            return 1

        return len(current_steps) + 1

    def _map_dependencies(self, analysis: Dict[str, Any], current_steps: List[Step]) -> List[str]:
        dependency_ids: List[str] = []
        if analysis.get('dependencies'):
            for dep_order in analysis['dependencies']:
                dep_step = next((s for s in current_steps if s.order == dep_order), None)
                if dep_step:
                    dependency_ids.append(dep_step.id)
        return dependency_ids

    def _normalize_agents(self, agent_field: Any) -> List[str]:
        if not agent_field:
            return []

        if isinstance(agent_field, list):
            raw_agents = agent_field
        else:
            cleaned = re.sub(r"\band\b", ",", str(agent_field), flags=re.IGNORECASE)
            raw_agents = re.split(r",|;|\n", cleaned)

        agents = [agent.strip() for agent in raw_agents if agent and agent.strip()]
        return agents

    def _normalize_tasks(self, task_field: Any, count: int) -> List[str]:
        if not task_field:
            return [""] * max(count, 1)

        if isinstance(task_field, list):
            tasks = [str(item).strip() for item in task_field if str(item).strip()]
        else:
            parts = re.split(r";|\n|\||\d+\.", str(task_field))
            tasks = [part.strip(" -") for part in parts if part.strip(" -")]

        if not tasks:
            tasks = [str(task_field).strip()]

        if len(tasks) == 1 and count > 1:
            and_splits = [segment.strip(" -") for segment in re.split(r"\band\b", tasks[0], flags=re.IGNORECASE) if segment.strip(" -")]
            if len(and_splits) >= count:
                tasks = and_splits

        while len(tasks) < count:
            tasks.append(tasks[-1])

        if len(tasks) > count:
            tasks = tasks[:count]

        return tasks

    def _normalize_functions(self, function_field: Any, count: int) -> List[str]:
        if not function_field:
            return [""] * count

        if isinstance(function_field, list):
            functions = [str(item).strip() for item in function_field if str(item).strip()]
        else:
            functions = [token.strip() for token in re.split(r",|;|\n", str(function_field)) if token.strip()]

        if not functions:
            functions = [""] * count

        while len(functions) < count:
            functions.append(functions[-1])

        if len(functions) > count:
            functions = functions[:count]

        return functions

    def _resolve_agent(self, agent_name: str) -> AgentType:
        normalized = (agent_name or '').strip()
        if not normalized:
            return AgentType.GENERIC

        normalized = normalized.replace(" ", "_")
        if not normalized.endswith("_Agent"):
            normalized = f"{normalized}_Agent"

        for agent in AgentType:
            if agent.value.lower() == normalized.lower():
                return agent

        logger.warning("TaskInjector: Unknown agent, defaulting to Generic", agent_name=agent_name)
        return AgentType.GENERIC
