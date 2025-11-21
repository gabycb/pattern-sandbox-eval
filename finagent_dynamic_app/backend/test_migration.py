"""
Migration Validation Test Suite for Agent Framework 1.0.0b251120

Tests all agents to ensure compatibility with the new framework version.
"""

import os
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    # Ensure aiodns-based credentials work on Windows where Proactor loop is default.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add app to path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import structlog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.infra.settings import Settings
from app.maf.agent_factory import MAFAgentFactory
from app.maf.planning import MAFDynamicPlanner

# Import all custom agents
from app.agents.company_agent import CompanyAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.agents.forecaster_agent import ForecasterAgent
from app.agents.technicals_agent import TechnicalsAgent
from app.agents.fundamentals_agent import FundamentalsAgent
from app.agents.sec_agent import SECAgent
from app.agents.earnings_agent import EarningsAgent
from app.agents.report_agent import ReportAgent

logger = structlog.get_logger(__name__)


class MigrationValidator:
    """Validates agent framework migration."""
    
    def __init__(self):
        self.settings = Settings()
        self.results: Dict[str, Dict[str, Any]] = {}
        self.factory: MAFAgentFactory | None = None
        
    async def initialize(self):
        """Initialize agent factory."""
        logger.info("Initializing MAFAgentFactory...")
        try:
            # Set event loop policy before creating factory (Windows compatibility)
            import sys
            if sys.platform == 'win32':
                loop = asyncio.get_event_loop()
                if not isinstance(loop, asyncio.ProactorEventLoop):
                    logger.info("Setting ProactorEventLoop for Windows Azure credentials")
            
            self.factory = MAFAgentFactory(self.settings)
            await self.factory.prepare()
            logger.info("✅ MAFAgentFactory initialized successfully")
            self.results["factory_init"] = {"status": "✅ PASS", "error": None}
            return True
        except Exception as e:
            logger.error("❌ Factory initialization failed", error=str(e))
            self.results["factory_init"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_imports(self):
        """Test that all framework imports work."""
        logger.info("\n=== Testing Framework Imports ===")
        try:
            from agent_framework import (
                BaseAgent,
                ChatAgent,
                ChatMessage,
                Role,
                TextContent,
                AgentRunResponse,
                AgentRunResponseUpdate,
                AgentThread
            )
            from agent_framework.azure import AzureAIAgentClient
            from agent_framework.observability import get_tracer, setup_observability
            
            logger.info("✅ All imports successful")
            self.results["imports"] = {"status": "✅ PASS", "error": None}
            return True
        except Exception as e:
            logger.error("❌ Import failed", error=str(e))
            self.results["imports"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_planner_agent(self):
        """Test Planner Agent (ChatAgent via factory)."""
        logger.info("\n=== Testing Planner Agent ===")
        try:
            # Create planner agent
            planner_agent = self.factory.create_chat_agent("planner")
            planner = MAFDynamicPlanner(planner_agent)
            
            # Test plan generation
            objective = "Analyze MSFT with focus on fundamentals and recent earnings"
            logger.info("Generating test plan...", objective=objective)
            
            plan = await planner.generate_plan(
                objective=objective,
                ticker="MSFT",
                summary_type="executive",
                persona="investment"
            )
            
            logger.info(f"✅ Plan generated with {len(plan)} steps")
            for step in plan:
                logger.info(f"  Step {step.order}: {step.agent} - {step.tool}")
            
            self.results["planner"] = {
                "status": "✅ PASS",
                "steps": len(plan),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Planner test failed", error=str(e))
            self.results["planner"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_summarizer_agent(self):
        """Test Summarizer Agent."""
        logger.info("\n=== Testing Summarizer Agent ===")
        try:
            # Get chat client for the agent
            chat_client = self.factory.get_agent_client("summarizer")
            
            # Create summarizer
            summarizer = SummarizerAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name
            )
            
            # Test run
            task = "Summarize: Apple announced strong Q4 earnings with revenue growth of 15%."
            logger.info("Testing summarizer...", task=task[:50])
            
            result = await summarizer.run(
                messages=task,
                context={"ticker": "AAPL"}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Summarizer agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["summarizer"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Summarizer test failed", error=str(e))
            self.results["summarizer"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_forecaster_agent(self):
        """Test Forecaster Agent."""
        logger.info("\n=== Testing Forecaster Agent ===")
        try:
            chat_client = self.factory.get_agent_client("forecaster")
            
            forecaster = ForecasterAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name
            )
            
            task = "Predict stock movement based on positive Q4 earnings and analyst upgrades"
            logger.info("Testing forecaster...", task=task[:50])
            
            context = {
                "ticker": "MSFT",
                "analysis_data": {
                    "news": "Strong earnings, CEO optimistic",
                    "recommendations": "3 analyst upgrades this week"
                }
            }
            
            result = await forecaster.run(messages=task, context=context)
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Forecaster agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["forecaster"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Forecaster test failed", error=str(e))
            self.results["forecaster"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_technicals_agent(self):
        """Test Technical Analysis Agent."""
        logger.info("\n=== Testing Technicals Agent ===")
        try:
            chat_client = self.factory.get_agent_client("technicals")
            
            technicals = TechnicalsAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name
            )
            
            task = "Analyze technical indicators for AAPL"
            logger.info("Testing technicals agent...", task=task)
            
            result = await technicals.run(
                messages=task,
                context={"ticker": "AAPL", "days": 90}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Technicals agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["technicals"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Technicals test failed", error=str(e))
            self.results["technicals"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_fundamentals_agent(self):
        """Test Fundamentals Agent."""
        logger.info("\n=== Testing Fundamentals Agent ===")
        try:
            chat_client = self.factory.get_agent_client("fundamentals")
            
            fundamentals = FundamentalsAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name,
                fmp_api_key=self.settings.fmp_api_key
            )
            
            task = "Analyze fundamental financial ratios for GOOGL"
            logger.info("Testing fundamentals agent...", task=task)
            
            result = await fundamentals.run(
                messages=task,
                context={"ticker": "GOOGL", "years": 3}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Fundamentals agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["fundamentals"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Fundamentals test failed", error=str(e))
            self.results["fundamentals"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_company_agent(self):
        """Test Company Agent."""
        logger.info("\n=== Testing Company Agent ===")
        try:
            chat_client = self.factory.get_agent_client("company")
            
            company = CompanyAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name,
                fmp_api_key=self.settings.fmp_api_key,
                mcp_server_url=self.settings.yahoo_finance_mcp_url
            )
            
            task = "Get company profile and stock info for NVDA"
            logger.info("Testing company agent...", task=task)
            
            result = await company.run(
                messages=task,
                context={"ticker": "NVDA"}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Company agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["company"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Company test failed", error=str(e))
            self.results["company"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_sec_agent(self):
        """Test SEC Agent."""
        logger.info("\n=== Testing SEC Agent ===")
        try:
            chat_client = self.factory.get_agent_client("sec")
            
            sec = SECAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name,
                fmp_api_key=self.settings.fmp_api_key
            )
            
            task = "Analyze 10-K filing highlights for TSLA"
            logger.info("Testing SEC agent...", task=task)
            
            result = await sec.run(
                messages=task,
                context={"ticker": "TSLA", "year": "latest", "report_type": "10-K"}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ SEC agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["sec"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ SEC test failed", error=str(e))
            self.results["sec"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_earnings_agent(self):
        """Test Earnings Agent."""
        logger.info("\n=== Testing Earnings Agent ===")
        try:
            chat_client = self.factory.get_agent_client("earnings")
            
            earnings = EarningsAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name,
                fmp_api_key=self.settings.fmp_api_key
            )
            
            task = "Summarize latest earnings call for META"
            logger.info("Testing earnings agent...", task=task)
            
            result = await earnings.run(
                messages=task,
                context={"ticker": "META", "year": "latest"}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Earnings agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["earnings"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Earnings test failed", error=str(e))
            self.results["earnings"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_report_agent(self):
        """Test Report Agent."""
        logger.info("\n=== Testing Report Agent ===")
        try:
            chat_client = self.factory.get_agent_client("report")
            
            report = ReportAgent(
                chat_client=chat_client,
                model=self.settings.azure_ai_model_deployment_name
            )
            
            task = "Generate equity research brief"
            logger.info("Testing report agent...", task=task)
            
            # Mock artifacts
            artifacts = [
                {"type": "company_profile", "ticker": "AAPL", "content": "Strong tech company"},
                {"type": "technical_analysis", "ticker": "AAPL", "content": "Bullish trend"},
            ]
            
            result = await report.run(
                messages=task,
                context={"ticker": "AAPL", "artifacts": artifacts}
            )
            
            assert result.messages, "No messages in response"
            assert result.messages[0].text, "No text in message"
            
            logger.info("✅ Report agent test passed")
            logger.info(f"  Response length: {len(result.messages[0].text)} chars")
            
            self.results["report"] = {
                "status": "✅ PASS",
                "response_length": len(result.messages[0].text),
                "error": None
            }
            return True
        except Exception as e:
            logger.error("❌ Report test failed", error=str(e))
            self.results["report"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    def print_summary(self):
        """Print test results summary."""
        logger.info("\n" + "="*70)
        logger.info("MIGRATION VALIDATION SUMMARY")
        logger.info("="*70)
        
        total_tests = len(self.results)
        passed = sum(1 for r in self.results.values() if "✅" in r["status"])
        failed = total_tests - passed
        
        for test_name, result in self.results.items():
            logger.info(f"{test_name:20s}: {result['status']}")
            if result['error']:
                logger.info(f"  Error: {result['error'][:100]}")
        
        logger.info("="*70)
        logger.info(f"TOTAL: {passed}/{total_tests} tests passed")
        
        if failed == 0:
            logger.info("✅ ALL TESTS PASSED - Migration is successful!")
        else:
            logger.info(f"⚠️ {failed} test(s) failed - Review errors above")
        
        logger.info("="*70)
        
        return failed == 0


async def main():
    """Run migration validation."""
    # Set event loop policy for Windows
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
        ]
    )
    
    logger.info("="*70)
    logger.info("Agent Framework Migration Validation")
    logger.info("Version: 1.0.0b251120")
    logger.info("="*70)
    
    validator = MigrationValidator()
    
    # Phase 0: Initialization
    logger.info("\n=== PHASE 0: Pre-Migration Validation ===")
    if not await validator.test_imports():
        logger.error("Import test failed. Aborting.")
        return False
    
    if not await validator.initialize():
        logger.error("Factory initialization failed. Aborting.")
        return False
    
    # Phase 1: Planner
    logger.info("\n=== PHASE 1: Planner Agent ===")
    await validator.test_planner_agent()
    
    # Phase 2-9: Custom Agents
    logger.info("\n=== PHASE 2-9: Custom Agents ===")
    await validator.test_summarizer_agent()
    await validator.test_forecaster_agent()
    await validator.test_technicals_agent()
    await validator.test_fundamentals_agent()
    await validator.test_company_agent()
    await validator.test_sec_agent()
    await validator.test_earnings_agent()
    await validator.test_report_agent()
    
    # Print summary
    success = validator.print_summary()
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
