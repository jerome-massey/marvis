"""Core troubleshooting orchestration logic for the Marvis module."""

import logging
from typing import Dict, List, Any, Optional, Union

from .config_loader import MarvisSettings
from .data_models import (
    AlarmDetails,
    TargetScope,
    UserQueryInput,
    TroubleshootingReport,
    InterimChatResponse,
    SupportedCapabilities,
    LLMDataRequestAction, # For LLM to request data
    LLMAnalysisResult, # For LLM to provide final analysis
    PyATSCommandResult, # For pyATS results
    ConnectivityTestResult # For connectivity test results
)
from .llm_handler import LLMHandler
# from .pyats_handler import PyATSHandler # Assuming this will be created
# from .report_builder import ReportBuilder # Assuming this will be created

logger = logging.getLogger(__name__)


class TroubleshootingManager:
    """
    Manages the overall troubleshooting workflow, orchestrating LLM interactions,
    pyATS data collection, and report generation.
    """

    def __init__(self, settings: MarvisSettings):
        """
        Initializes the TroubleshootingManager.

        Args:
            settings: Configuration settings for the Marvis module.
        """
        self.settings = settings
        logger.info("Initializing TroubleshootingManager...")

        # Initialize LLM Handler (FR1)
        # Pydantic AI uses underlying LLM SDKs. Config is passed to LLMHandler.
        llm_handler_config = {
            "provider": settings.llm.provider,
            "api_key": settings.llm.api_key.get_secret_value() if settings.llm.api_key else None,
            "model_name": settings.llm.model_name,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
            # System prompt templates can be part of llm_handler's internal config
            # or passed here if they need to be more dynamic from MarvisSettings
        }
        self.llm_handler = LLMHandler(llm_config=llm_handler_config)
        logger.info(f"LLMHandler initialized with provider: {settings.llm.provider}, model: {settings.llm.model_name}")

        # Initialize pyATS Handler (FR6, FR7, FR8, FR9)
        # self.pyats_handler = PyATSHandler(
        #     testbed_file=settings.pyats.testbed_file,
        #     allowed_commands=settings.allowed_pyats_commands,
        #     enable_connectivity_tests=settings.features.enable_basic_connectivity_tests_on_failure
        # )
        # logger.info("PyATSHandler initialized.")
        # Placeholder for PyATSHandler initialization
        self.pyats_handler = None # Replace with actual PyATSHandler instance
        logger.warning("PyATSHandler is not yet implemented and initialized.")


        # Initialize Report Builder (FR13, FR14)
        # self.report_builder = ReportBuilder()
        # logger.info("ReportBuilder initialized.")
        # Placeholder for ReportBuilder initialization
        self.report_builder = None # Replace with actual ReportBuilder instance
        logger.warning("ReportBuilder is not yet implemented and initialized.")

        logger.info("TroubleshootingManager initialized successfully.")

    async def process_alarm(
        self, alarm_details: AlarmDetails, target_scope: TargetScope
    ) -> TroubleshootingReport:
        """
        Processes an alarm-triggered troubleshooting request. (FR16)

        Orchestrates LLM interaction (via Pydantic AI) and pyATS usage
        based on alarm context.

        Args:
            alarm_details: Structured information about the alarm.
            target_scope: Defines the scope of the troubleshooting.

        Returns:
            A dictionary containing the troubleshooting report.
        """
        logger.info(f"Processing alarm: {alarm_details.description[:50]}... for target: {target_scope.model_dump_json()}")
        
        # 1. Initial LLM interaction: Analyze alarm, suggest initial data gathering (FR2, FR3, FR5)
        #    - Formulate prompt with alarm details and capabilities.
        #    - Expect LLMDataRequestAction as output.
        
        # Example prompt content for the LLM
        initial_prompt_context = f"Alarm Received:\\nSeverity: {alarm_details.severity}\\nSource: {alarm_details.source}\\nAffected: {alarm_details.affected_component}\\nDescription: {alarm_details.description}"
        if alarm_details.additional_info:
            initial_prompt_context += f"\\nAdditional Info: {alarm_details.additional_info}"

        initial_user_query = "Based on the provided alarm details, what initial set of pyATS commands should be run to diagnose the issue? If you need to ask for clarification before suggesting commands, please do so."

        # capabilities_summary = f"Supported pyATS commands: {', '.join(self.settings.allowed_pyats_commands)}"
        # llm_data_request = await self.llm_handler.get_structured_response(
        #     user_query=initial_user_query,
        #     output_model=LLMDataRequestAction,
        #     current_context=initial_prompt_context,
        #     pyats_capabilities_summary=capabilities_summary
        # )
        # logger.debug(f"LLM suggested data request: {llm_data_request}")

        # 2. Execute pyATS commands based on LLMDataRequestAction (FR7, FR8)
        #    - Use self.pyats_handler.execute_commands(llm_data_request.pyats_commands, target_scope)
        #    - Handle errors, connectivity tests (FR9, FR9.1)
        # collected_pyats_results: List[PyATSCommandResult] = []
        # connectivity_results: List[ConnectivityTestResult] = []
        
        # if self.pyats_handler and llm_data_request.pyats_commands:
        #     # This part needs careful implementation in pyats_handler
        #     # For now, this is a conceptual flow
        #     pass # Placeholder for pyATS execution logic

        # 3. Second LLM interaction: Analyze collected data, provide assessment (FR3, FR5, FR11)
        #    - Formulate prompt with alarm, collected data.
        #    - Expect LLMAnalysisResult as output.
        # analysis_prompt_context = initial_prompt_context + "\\n\\nCollected Data:\\n" # Add formatted pyATS results
        # analysis_user_query = "Analyze the alarm details and the collected device data. Provide an overall assessment, key findings, potential root causes, and suggested next steps."
        
        # llm_analysis = await self.llm_handler.get_structured_response(
        #     user_query=analysis_user_query,
        #     output_model=LLMAnalysisResult,
        #     current_context=analysis_prompt_context # This would include formatted pyATS results
        # )
        # logger.debug(f"LLM analysis result: {llm_analysis}")

        # 4. Generate Report (FR13, FR14)
        #    - Use self.report_builder.generate_report(...)
        # report = TroubleshootingReport(
        #     request_type="alarm",
        #     original_request=alarm_details,
        #     target_scope=target_scope,
        #     # devices_investigated=...
        #     # pyats_command_results=collected_pyats_results,
        #     # connectivity_test_results=connectivity_results,
        #     # llm_analysis=llm_analysis
        # )
        
        # Placeholder implementation
        logger.warning("process_alarm is not fully implemented yet.")
        # This is a stub. Full implementation requires pyats_handler and report_builder.
        return TroubleshootingReport(
            request_type="alarm",
            original_request=alarm_details,
            target_scope=target_scope,
            investigation_summary="Placeholder: Alarm processing not fully implemented.",
            llm_analysis=LLMAnalysisResult(
                overall_assessment="Placeholder analysis.",
                key_findings=["Feature not implemented."],
                potential_root_causes=["Feature not implemented."],
                suggested_next_steps=["Implement process_alarm."]
            )
        )

    async def process_user_query(
        self, query_input: UserQueryInput
    ) -> Union[TroubleshootingReport, InterimChatResponse]:
        """
        Processes an interactive user query. (FR17)

        Orchestrates LLM interaction (via Pydantic AI) and pyATS usage
        based on user query and context. Can result in an interim chat response
        or a final troubleshooting report.

        Args:
            query_input: Contains the user's query, target scope, chat history, and file uploads.

        Returns:
            Either a TroubleshootingReport or an InterimChatResponse.
        """
        logger.info(f"Processing user query: {query_input.query[:50]}... for target: {query_input.target_scope.model_dump_json()}")
        
        # This method will involve a conversational loop:
        # 1. Prepare context: user query, chat history, file uploads, capabilities. (FR4, FR11)
        # 2. LLM interaction:
        #    - Ask LLM to decide next action:
        #      a) Request data via pyATS (LLMDataRequestAction) (FR5)
        #      b) Ask user for clarification (response as InterimChatResponse)
        #      c) Provide final analysis (LLMAnalysisResult, then build TroubleshootingReport)
        # 3. If data request:
        #    - Execute pyATS commands (self.pyats_handler) (FR7, FR8, FR9)
        #    - Feed results back to LLM (goto step 2)
        # 4. If clarification:
        #    - Return InterimChatResponse to client.
        # 5. If final analysis:
        #    - Generate and return TroubleshootingReport. (FR13, FR14)

        # Placeholder implementation
        logger.warning("process_user_query is not fully implemented yet.")
        # This is a stub. Full implementation requires more complex logic.
        if "report" in query_input.query.lower(): # Simple heuristic for testing
            return TroubleshootingReport(
                request_type="user_query",
                original_request=query_input,
                target_scope=query_input.target_scope,
                investigation_summary="Placeholder: User query processing for report not fully implemented.",
                 llm_analysis=LLMAnalysisResult(
                    overall_assessment="Placeholder analysis for user query.",
                    key_findings=["Feature not implemented."],
                    potential_root_causes=["Feature not implemented."],
                    suggested_next_steps=["Implement process_user_query for reports."]
                )
            )
        else:
            return InterimChatResponse(
                assistant_message="Placeholder: I am not yet fully equipped to handle this query. The 'process_user_query' method needs to be implemented."
            )

    def get_supported_capabilities(self) -> SupportedCapabilities:
        """
        Returns the data gathering capabilities of the module. (FR5 - informing LLM)

        This primarily lists supported pyATS commands.

        Returns:
            A dictionary describing supported capabilities.
        """
        logger.debug("Fetching supported capabilities.")
        return SupportedCapabilities(
            supported_pyats_commands=self.settings.allowed_pyats_commands
        )

# Example usage (for testing, typically not in the module itself)
async def main_test():
    import asyncio
    from .config_loader import load_marvis_settings
    
    # Configure logging for visibility
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger.info("Starting TroubleshootingManager test...")
    
    # Load settings (ensure .env or environment variables are set for LLM API key)
    # Example .env content:
    # MARVIS_LLM__PROVIDER="openai" # or "google"
    # MARVIS_LLM__API_KEY="sk-your-openai-api-key" # or your Google API key
    # MARVIS_LLM__MODEL_NAME="gpt-4o" # or "gemini-1.5-flash-latest"
    # MARVIS_PYATS__TESTBED_FILE="dummy_testbed.yaml" # Optional, not used by current stubs
    
    try:
        settings = load_marvis_settings()
        if not settings.llm.api_key or not settings.llm.api_key.get_secret_value():
            logger.error("LLM API key is not set. Please set MARVIS_LLM__API_KEY environment variable.")
            print("LLM API key is missing. Please set it in your environment (e.g., .env file as MARVIS_LLM__API_KEY).")
            return
        
        manager = TroubleshootingManager(settings)

        # Test get_supported_capabilities
        capabilities = manager.get_supported_capabilities()
        logger.info(f"Supported capabilities: {capabilities.model_dump_json(indent=2)}")
        print(f"Supported pyATS Commands: {capabilities.supported_pyats_commands}")

        # Test process_alarm (stubbed)
        alarm = AlarmDetails(
            source="TestSystem",
            severity="Critical",
            affected_component="DeviceA/Interface1",
            description="Interface is down unexpectedly."
        )
        scope = TargetScope(device_hostnames=["DeviceA"])
        # alarm_report = await manager.process_alarm(alarm, scope)
        # logger.info(f"Alarm report (stubbed): {alarm_report.model_dump_json(indent=2)}")
        # print(f"Alarm Report (stubbed): {alarm_report.llm_analysis.overall_assessment}")

        # Test process_user_query (stubbed - interim response)
        user_query_interim = UserQueryInput(
            query="My internet is slow, what can I do?",
            target_scope=TargetScope(device_hostnames=["Router1", "Modem1"])
        )
        # interim_response = await manager.process_user_query(user_query_interim)
        # logger.info(f"User query interim response (stubbed): {interim_response.model_dump_json(indent=2)}")
        # if isinstance(interim_response, InterimChatResponse):
        #     print(f"Interim Chat Response (stubbed): {interim_response.assistant_message}")


        # Test process_user_query (stubbed - report response)
        user_query_report = UserQueryInput(
            query="Please generate a report for connectivity issues on RouterX.",
            target_scope=TargetScope(device_hostnames=["RouterX"])
        )
        # final_report_user_query = await manager.process_user_query(user_query_report)
        # logger.info(f"User query final report (stubbed): {final_report_user_query.model_dump_json(indent=2)}")
        # if isinstance(final_report_user_query, TroubleshootingReport):
        #     print(f"User Query Report (stubbed): {final_report_user_query.llm_analysis.overall_assessment}")
        
        logger.info("Note: process_alarm and process_user_query are currently stubbed and do not make live LLM calls in this test.")
        print("\\nNote: process_alarm and process_user_query in the manager are currently high-level stubs.")
        print("Full implementation will require pyats_handler, report_builder, and more detailed orchestration logic.")
        print("The LLMHandler itself is functional if API keys are correctly configured.")


    except Exception as e:
        logger.error(f"Error during manager test: {e}", exc_info=True)
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # This main_test is for illustrative purposes.
    # To run it, you would execute this file directly (python -m marvis.manager)
    # Ensure your environment (e.g. .env file at project root) has MARVIS_LLM__API_KEY.
    # Example:
    # MARVIS_LLM__PROVIDER="openai"
    # MARVIS_LLM__API_KEY="your_actual_openai_api_key"
    # MARVIS_LLM__MODEL_NAME="gpt-4o"

    # asyncio.run(main_test())
    print("To run the test main function, uncomment 'asyncio.run(main_test())' and ensure LLM API keys are set.")
    print("Example .env content for LLM (place in project root, next to pyproject.toml):")
    print("MARVIS_LLM__PROVIDER=\"openai\"")
    print("MARVIS_LLM__API_KEY=\"your-api-key\"")
    print("MARVIS_LLM__MODEL_NAME=\"gpt-4o\"")