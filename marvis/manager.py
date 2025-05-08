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
from .pyats_handler import PyATSHandler # Assuming this will be created
from .report_builder import ReportBuilder # Assuming this will be created

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
        llm_handler_config = {
            "provider": settings.llm.provider,
            "api_key": settings.llm.api_key.get_secret_value() if settings.llm.api_key else None,
            "model_name": settings.llm.model_name,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
            # Consider adding system_prompt_template and pyats_capabilities_prompt_section
            # from settings if they are to be configurable at this level.
            # For now, llm_handler uses its defaults or those passed here.
        }
        self.llm_handler = LLMHandler(llm_config=llm_handler_config)
        logger.info(f"LLMHandler initialized with provider: {settings.llm.provider}, model: {settings.llm.model_name}")

        # Initialize pyATS Handler (FR6, FR7, FR8, FR9)
        try:
            self.pyats_handler = PyATSHandler(
                testbed_file=settings.pyats.testbed_file, # Can be None
                allowed_commands=settings.allowed_pyats_commands,
                enable_connectivity_tests=settings.features.enable_basic_connectivity_tests_on_failure
            )
            logger.info("PyATSHandler initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize PyATSHandler: {e}", exc_info=True)
            self.pyats_handler = None # Ensure it's None if initialization fails
            logger.warning("PyATSHandler is not available due to initialization error.")


        # Initialize Report Builder (FR13, FR14)
        try:
            self.report_builder = ReportBuilder()
            logger.info("ReportBuilder initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize ReportBuilder: {e}", exc_info=True)
            self.report_builder = None # Ensure it's None if initialization fails
            logger.warning("ReportBuilder is not available due to initialization error.")

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
            A TroubleshootingReport object.
        """
        logger.info(f"Processing alarm: '{alarm_details.description[:50]}...' for target: {target_scope.model_dump_json(exclude_none=True)}")
        
        investigated_devices: List[str] = target_scope.device_hostnames or []
        collected_pyats_results: List[PyATSCommandResult] = []
        connectivity_test_results_agg: List[ConnectivityTestResult] = []
        llm_analysis_result: Optional[LLMAnalysisResult] = None
        investigation_summary = f"Initial investigation for alarm: {alarm_details.description}"

        # 1. Initial LLM interaction: Analyze alarm, suggest initial data gathering (FR2, FR3, FR5)
        capabilities_summary = f"Supported pyATS commands include: {', '.join(self.settings.allowed_pyats_commands)}. " \
                               "Focus on commands relevant to the alarm."
        
        initial_context_parts = [
            f"Alarm Received:",
            f"  Severity: {alarm_details.severity}",
            f"  Source: {alarm_details.source}",
            f"  Affected Component: {alarm_details.affected_component}",
            f"  Description: {alarm_details.description}"
        ]
        if alarm_details.additional_info:
            initial_context_parts.append(f"  Additional Info: {alarm_details.additional_info}")
        
        initial_context_str = "\\n".join(initial_context_parts)
        
        initial_llm_query = (
            "Based on the provided alarm details, what initial set of pyATS commands should be run "
            "on the target devices to diagnose the issue? "
            "Please specify which commands to run on which devices if applicable. "
            "If you need to ask for clarification before suggesting commands, use the 'ask_user_clarification' field."
        )

        try:
            logger.debug("Attempting first LLM call for data gathering suggestions.")
            llm_data_request = await self.llm_handler.get_structured_response(
                user_query=initial_llm_query,
                output_model=LLMDataRequestAction,
                current_context=initial_context_str,
                pyats_capabilities_summary=capabilities_summary
            )
            logger.info(f"LLM suggested data request: {llm_data_request.thought or 'No thought provided.'}")

            if llm_data_request.ask_user_clarification:
                logger.info(f"LLM asked for clarification: {llm_data_request.ask_user_clarification}")
                # For alarm processing, direct clarification might be complex.
                # We'll log it and proceed if commands were also given, or report it.
                investigation_summary += f" LLM requested clarification: {llm_data_request.ask_user_clarification}"

            # 2. Execute pyATS commands based on LLMDataRequestAction (FR7, FR8)
            if self.pyats_handler and llm_data_request.pyats_commands:
                logger.info(f"Executing {len(llm_data_request.pyats_commands)} command(s) via PyATSHandler.")
                # This part needs to be fleshed out when PyATSHandler is fully implemented.
                # For now, a simplified loop.
                for cmd_req in llm_data_request.pyats_commands:
                    devices_to_run_on = cmd_req.devices or target_scope.device_hostnames or []
                    if not devices_to_run_on:
                        logger.warning(f"No target devices specified for command '{cmd_req.command}', skipping.")
                        continue
                    
                    # Conceptual: pyats_handler.execute_commands_on_devices would handle multiple devices
                    # For now, let's assume it processes one command on multiple devices.
                    # results, conn_tests = await self.pyats_handler.execute_command_on_devices(
                    #     devices=devices_to_run_on,
                    #     command=cmd_req.command
                    # )
                    # collected_pyats_results.extend(results)
                    # connectivity_test_results_agg.extend(conn_tests)
                    logger.warning(f"PyATS command execution for '{cmd_req.command}' is stubbed.")
                    # Add dummy results for now to allow flow to continue
                    for device_name in devices_to_run_on:
                        collected_pyats_results.append(PyATSCommandResult(
                            device_hostname=device_name,
                            command=cmd_req.command,
                            raw_output=f"Stubbed output for {cmd_req.command} on {device_name}",
                            error="Stubbed execution - PyATSHandler not fully integrated."
                        ))
                investigation_summary += f" Attempted to run {len(llm_data_request.pyats_commands)} types of commands."
            elif not self.pyats_handler:
                logger.warning("PyATSHandler not available. Skipping command execution.")
                investigation_summary += " PyATSHandler not available, commands not executed."
            else:
                logger.info("LLM did not request any pyATS commands.")
                investigation_summary += " LLM did not request specific pyATS commands."

        except Exception as e:
            logger.error(f"Error during initial LLM interaction or pyATS execution: {e}", exc_info=True)
            investigation_summary += f" Error encountered: {e}."
        
        # 3. Second LLM interaction: Analyze collected data, provide assessment (FR3, FR5, FR11)
        if collected_pyats_results: # Only proceed if there's data to analyze
            analysis_context_parts = [initial_context_str, "\\nCollected pyATS Data:"]
            for res in collected_pyats_results:
                analysis_context_parts.append(
                    f"  Device: {res.device_hostname}, Command: {res.command}"
                )
                if res.parsed_output:
                    analysis_context_parts.append(f"    Parsed: {str(res.parsed_output)[:200]}...") # Truncate for brevity
                elif res.raw_output:
                    analysis_context_parts.append(f"    Raw: {res.raw_output[:200]}...") # Truncate
                if res.error:
                    analysis_context_parts.append(f"    Error: {res.error}")
            
            if connectivity_test_results_agg:
                analysis_context_parts.append("\\nConnectivity Test Results:")
                for conn_test in connectivity_test_results_agg:
                    analysis_context_parts.append(
                        f"  Target: {conn_test.target}, Type: {conn_test.test_type}, Success: {conn_test.success}, Details: {conn_test.details}"
                    )
            
            analysis_context_str = "\\n".join(analysis_context_parts)
            analysis_llm_query = (
                "Analyze the alarm details and the collected device data (and any connectivity test results). "
                "Provide an overall assessment, key findings, potential root causes, and suggested next steps. "
                "Be concise and focus on actionable insights."
            )
            try:
                logger.debug("Attempting second LLM call for analysis.")
                llm_analysis_result = await self.llm_handler.get_structured_response(
                    user_query=analysis_llm_query,
                    output_model=LLMAnalysisResult,
                    current_context=analysis_context_str
                )
                logger.info(f"LLM analysis received: {llm_analysis_result.overall_assessment[:100]}...")
                investigation_summary += " LLM analysis performed on collected data."
            except Exception as e:
                logger.error(f"Error during LLM analysis phase: {e}", exc_info=True)
                investigation_summary += f" Error during LLM analysis: {e}."
                llm_analysis_result = LLMAnalysisResult( # Provide a fallback
                    overall_assessment="Error during LLM analysis.",
                    key_findings=[f"Exception: {e}"],
                    potential_root_causes=["LLM analysis failed."],
                    suggested_next_steps=["Review logs for errors."]
                )
        elif not llm_data_request.ask_user_clarification: # If no data and no clarification, make a simple assessment
             try:
                logger.debug("No pyATS data, attempting simple LLM assessment based on alarm.")
                simple_assessment_query = (
                    "Based on the alarm details alone, provide a very brief initial assessment and "
                    "suggest generic next steps or checks that could be performed manually, "
                    "as no automated commands were run or data was collected."
                )
                llm_analysis_result = await self.llm_handler.get_structured_response(
                    user_query=simple_assessment_query,
                    output_model=LLMAnalysisResult,
                    current_context=initial_context_str
                )
                investigation_summary += " LLM provided assessment based on alarm details only."
             except Exception as e:
                logger.error(f"Error during simple LLM assessment: {e}", exc_info=True)
                investigation_summary += f" Error during simple LLM assessment: {e}."
                llm_analysis_result = LLMAnalysisResult(
                    overall_assessment="Error during initial LLM assessment (no data collected).",
                    key_findings=[f"Exception: {e}"],
                    potential_root_causes=["LLM assessment failed."],
                    suggested_next_steps=["Review logs for errors, check alarm source."]
                )


        # 4. Generate Report (FR13, FR14)
        # If ReportBuilder is available, use it. Otherwise, construct directly.
        final_report: TroubleshootingReport
        if self.report_builder:
            logger.debug("Using ReportBuilder to generate the report.")
            # final_report = self.report_builder.generate_report( # This method needs to be defined in ReportBuilder
            #     request_type="alarm",
            #     original_request=alarm_details,
            #     target_scope=target_scope,
            #     investigation_summary=investigation_summary,
            #     devices_investigated=investigated_devices, # This should be refined based on actual interactions
            #     pyats_command_results=collected_pyats_results,
            #     connectivity_test_results=connectivity_test_results_agg,
            #     llm_analysis=llm_analysis_result
            # )
            # Placeholder until ReportBuilder is implemented
            logger.warning("ReportBuilder.generate_report() is stubbed.")
            final_report = TroubleshootingReport(
                request_type="alarm",
                original_request=alarm_details,
                target_scope=target_scope,
                investigation_summary=investigation_summary,
                devices_investigated=investigated_devices,
                pyats_command_results=collected_pyats_results,
                connectivity_test_results=connectivity_test_results_agg,
                llm_analysis=llm_analysis_result
            )
        else:
            logger.warning("ReportBuilder not available. Constructing report directly in manager.")
            final_report = TroubleshootingReport(
                request_type="alarm",
                original_request=alarm_details,
                target_scope=target_scope,
                investigation_summary=investigation_summary,
                devices_investigated=investigated_devices, # Refine based on actual device interaction
                pyats_command_results=collected_pyats_results,
                connectivity_test_results=connectivity_test_results_agg,
                llm_analysis=llm_analysis_result
            )
        
        logger.info(f"Alarm processing complete for: '{alarm_details.description[:50]}...'")
        return final_report

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
        logger.info(f"Processing user query: {query_input.query[:50]}... for target: {query_input.target_scope.model_dump_json(exclude_none=True)}")

        # 1. Prepare context for the first LLM call
        # FR4: Conversation History Management (used from input)
        # FR11: Data Preparation for LLM
        chat_history_for_llm = []
        if query_input.chat_history:
            for msg in query_input.chat_history:
                chat_history_for_llm.append({"role": msg.role, "content": msg.content})

        current_context_parts = [f"User Query: {query_input.query}"]
        if query_input.target_scope:
            current_context_parts.append(f"Target Scope: {query_input.target_scope.model_dump_json(exclude_none=True)}")
        if query_input.file_uploads:
            current_context_parts.append("Uploaded Files:")
            for f_upload in query_input.file_uploads:
                current_context_parts.append(f"  - {f_upload.filename}: {f_upload.content[:100]}...") # Truncate content

        current_context_str = "\\n".join(current_context_parts)
        capabilities_summary = f"Supported pyATS commands: {', '.join(self.settings.allowed_pyats_commands)}. You can also ask for user clarification."

        # 2. First LLM call to decide action (clarify, get data, or simple thought)
        # FR2, FR3, FR5
        llm_prompt_for_action = (
            "Based on the user's query, chat history, target scope, and any uploaded files, determine the best course of action. "
            "You can: \\n"
            "1. Ask a clarifying question to the user (use 'ask_user_clarification').\\n"
            "2. Request specific pyATS commands to be run on devices (use 'pyats_commands').\\n"
            "3. Provide a direct thought or initial assessment if no immediate data is needed or if the query is general (use 'thought')."
        )
        
        try:
            logger.debug("Attempting LLM call for action planning in process_user_query.")
            llm_action_request = await self.llm_handler.get_structured_response(
                user_query=llm_prompt_for_action, # The query here is our instruction to the LLM
                output_model=LLMDataRequestAction,
                current_context=current_context_str, # User's actual query and context
                chat_history=chat_history_for_llm,
                pyats_capabilities_summary=capabilities_summary
            )
            logger.info(f"LLM suggested action: Thought: '{llm_action_request.thought}', Commands: {len(llm_action_request.pyats_commands or [])}, Clarification: '{llm_action_request.ask_user_clarification}'")

        except Exception as e:
            logger.error(f"Error during LLM action planning in process_user_query: {e}", exc_info=True)
            return InterimChatResponse(assistant_message=f"I encountered an error trying to understand your request: {e}")

        # 3. Process LLM's suggested action
        if llm_action_request.ask_user_clarification:
            logger.info(f"LLM requests clarification: {llm_action_request.ask_user_clarification}")
            return InterimChatResponse(assistant_message=llm_action_request.ask_user_clarification)

        elif llm_action_request.pyats_commands and self.pyats_handler:
            logger.info(f"LLM requests {len(llm_action_request.pyats_commands)} pyATS command(s). Executing (stubbed)...")
            collected_pyats_results: List[PyATSCommandResult] = []
            connectivity_test_results_agg: List[ConnectivityTestResult] = []
            
            # FR7, FR8, FR9 (Conceptual execution)
            for cmd_req in llm_action_request.pyats_commands:
                devices_to_run_on = cmd_req.devices or query_input.target_scope.device_hostnames or []
                if not devices_to_run_on:
                    logger.warning(f"No target devices for command '{cmd_req.command}', skipping.")
                    continue
                # This would be: results, conn_tests = await self.pyats_handler.execute_command_on_devices(...)
                logger.warning(f"PyATS command execution for '{cmd_req.command}' on {devices_to_run_on} is stubbed.")
                for device_name in devices_to_run_on:
                    collected_pyats_results.append(PyATSCommandResult(
                        device_hostname=device_name, command=cmd_req.command,
                        raw_output=f"Stubbed output for {cmd_req.command} on {device_name}",
                        error="Stubbed execution - PyATSHandler not fully integrated."
                    ))
            
            # Prepare context for the second LLM call (analysis)
            analysis_context_parts = [current_context_str, "\\nCollected pyATS Data:"]
            for res in collected_pyats_results:
                analysis_context_parts.append(f"  Device: {res.device_hostname}, Command: {res.command}, Output: {res.raw_output[:100]}... Error: {res.error}")
            # Add connectivity tests if available
            analysis_context_str = "\\n".join(analysis_context_parts)
            
            llm_prompt_for_analysis = (
                "Analyze the user's original request, conversation history, and the recently collected pyATS command results. "
                "Provide a comprehensive analysis including key findings, potential root causes, and suggested next steps. "
                "This will form the basis of a troubleshooting report or a detailed interim response."
            )
            try:
                logger.debug("Attempting LLM call for analysis after data collection.")
                llm_analysis = await self.llm_handler.get_structured_response(
                    user_query=llm_prompt_for_analysis,
                    output_model=LLMAnalysisResult,
                    current_context=analysis_context_str, # Includes original query + new data
                    chat_history=chat_history_for_llm 
                )
                logger.info(f"LLM analysis received: {llm_analysis.overall_assessment[:100]}...")
                
                # FR13, FR14: Generate and return TroubleshootingReport
                report = TroubleshootingReport(
                    request_type="user_query",
                    original_request=query_input,
                    target_scope=query_input.target_scope,
                    investigation_summary=f"Investigation based on user query and {len(collected_pyats_results)} executed commands (stubbed). LLM thought: {llm_action_request.thought or 'N/A'}",
                    devices_investigated=list(set(dr.device_hostname for dr in collected_pyats_results)),
                    pyats_command_results=collected_pyats_results,
                    connectivity_test_results=connectivity_test_results_agg,
                    llm_analysis=llm_analysis
                )
                # if self.report_builder: report = self.report_builder.generate_report(...) # Conceptual
                return report

            except Exception as e:
                logger.error(f"Error during LLM analysis in process_user_query: {e}", exc_info=True)
                return InterimChatResponse(assistant_message=f"I gathered some data but encountered an error during analysis: {e}")

        elif llm_action_request.pyats_commands and not self.pyats_handler:
            logger.warning("LLM requested pyATS commands, but PyATSHandler is not available.")
            return InterimChatResponse(assistant_message="I'd like to run some device commands, but I'm currently unable to connect to devices. Please check my configuration.")

        elif llm_action_request.thought:
            logger.info(f"LLM provided a thought: {llm_action_request.thought}")
            return InterimChatResponse(assistant_message=llm_action_request.thought)
            
        else: # LLM returned no specific action
            logger.warning("LLM did not suggest a clear action (no clarification, commands, or thought).")
            return InterimChatResponse(assistant_message="I'm not sure how to proceed with that. Could you please rephrase or provide more details?")

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
    # Ensure marvis.pyats_handler and marvis.report_builder exist or comment out their direct usage for test
    # For now, they are mocked/stubbed within the manager's __init__ if they fail to load.

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        
        # Create dummy pyats_handler.py and report_builder.py if they don't exist to allow manager to init
        # This is a hack for testing in isolation. In a real scenario, these files would exist.
        import os
        if not os.path.exists("marvis/pyats_handler.py"):
            with open("marvis/pyats_handler.py", "w") as f:
                f.write("""# Dummy pyats_handler.py for testing manager.py
class PyATSHandler:
    def __init__(self, *args, **kwargs): pass
    async def execute_command_on_devices(self, *args, **kwargs): return [], []
""")
        if not os.path.exists("marvis/report_builder.py"):
            with open("marvis/report_builder.py", "w") as f:
                f.write("""# Dummy report_builder.py for testing manager.py
class ReportBuilder:
    def __init__(self, *args, **kwargs): pass
    def generate_report(self, *args, **kwargs): return None # Should return TroubleshootingReport
""")

        manager = TroubleshootingManager(settings)

        # Test get_supported_capabilities
        capabilities = manager.get_supported_capabilities()
        logger.info(f"Supported capabilities: {capabilities.model_dump_json(indent=2)}")
        print(f"Supported pyATS Commands: {capabilities.supported_pyats_commands}")

        # Test process_alarm (now more fleshed out, but still uses stubbed pyATS and LLM calls here for safety)
        alarm = AlarmDetails(
            source="TestSystem",
            severity="Critical",
            affected_component="DeviceA/Interface1",
            description="Interface GigabitEthernet0/0/1 is down unexpectedly on router DC1-EDGE-01."
        )
        scope = TargetScope(device_hostnames=["DC1-EDGE-01"])
        
        print("\\n--- Testing process_alarm ---")
        alarm_report = await manager.process_alarm(alarm, scope)
        logger.info(f"Alarm report received. Overall Assessment: {alarm_report.llm_analysis.overall_assessment if alarm_report.llm_analysis else 'N/A'}")
        print(f"Alarm Report - Assessment: {alarm_report.llm_analysis.overall_assessment if alarm_report.llm_analysis else 'No LLM Analysis available'}")
        if alarm_report.pyats_command_results:
            print(f"  Commands considered/stubbed for alarm: {len(alarm_report.pyats_command_results)}")

        # Test process_user_query
        print("\\n--- Testing process_user_query (scenario: LLM asks for clarification) ---")
        # Mock LLMHandler to control its response for this specific test case
        original_llm_handler_get_response = manager.llm_handler.get_structured_response
        
        async def mock_llm_clarification(*args, **kwargs):
            if kwargs.get('output_model') == LLMDataRequestAction:
                print("    (Mocking LLM to ask for clarification...)")
                return LLMDataRequestAction(ask_user_clarification="Could you please specify which building you are in?")
            return await original_llm_handler_get_response(*args, **kwargs)

        manager.llm_handler.get_structured_response = mock_llm_clarification
        user_query_clarify = UserQueryInput(
            query="My internet is slow.",
            target_scope=TargetScope(market_or_region="CityCampus")
        )
        response_clarify = await manager.process_user_query(user_query_clarify)
        manager.llm_handler.get_structured_response = original_llm_handler_get_response # Restore
        
        if isinstance(response_clarify, InterimChatResponse):
            print(f"User Query (Clarification) - Assistant: {response_clarify.assistant_message}")
            assert "specify which building" in response_clarify.assistant_message
        else:
            print(f"User Query (Clarification) - Unexpected response type: {type(response_clarify)}")


        print("\\n--- Testing process_user_query (scenario: LLM requests commands, then report) ---")
        async def mock_llm_commands_then_analysis(*args, **kwargs):
            if kwargs.get('output_model') == LLMDataRequestAction:
                print("    (Mocking LLM to request 'show version' and 'show ip int brief'...)")
                return LLMDataRequestAction(
                    thought="User reports slowness, let's check basic device status.",
                    pyats_commands=[
                        PyATSCommandRequest(command="show version", devices=kwargs.get('current_context', '').split('Device: ')[-1].split('\\n')[0] if 'Device: ' in kwargs.get('current_context', '') else ['RouterA']), # Simplistic device extraction for mock
                        PyATSCommandRequest(command="show ip interface brief", devices=kwargs.get('current_context', '').split('Device: ')[-1].split('\\n')[0] if 'Device: ' in kwargs.get('current_context', '') else ['RouterA'])
                    ]
                )
            elif kwargs.get('output_model') == LLMAnalysisResult:
                print("    (Mocking LLM to provide analysis after (stubbed) commands...)")
                return LLMAnalysisResult(
                    overall_assessment="Devices appear to be online, but interface brief shows some down. User should check physical connections.",
                    key_findings=["Stubbed 'show version' looked okay.", "Stubbed 'show ip interface brief' indicated some interfaces are down."],
                    potential_root_causes=["Physical layer issue on some interfaces.", "Misconfiguration."],
                    suggested_next_steps=["Verify physical cabling for down interfaces.", "Check interface configurations."]
                )
            return await original_llm_handler_get_response(*args, **kwargs) # Fallback

        manager.llm_handler.get_structured_response = mock_llm_commands_then_analysis
        user_query_commands = UserQueryInput(
            query="Network is very slow in the West Wing. Check Device: WestWingRouter.",
            target_scope=TargetScope(device_hostnames=["WestWingRouter"])
        )
        response_commands = await manager.process_user_query(user_query_commands)
        manager.llm_handler.get_structured_response = original_llm_handler_get_response # Restore

        if isinstance(response_commands, TroubleshootingReport):
            print(f"User Query (Commands & Report) - Assessment: {response_commands.llm_analysis.overall_assessment if response_commands.llm_analysis else 'N/A'}")
            assert response_commands.pyats_command_results is not None and len(response_commands.pyats_command_results) > 0
            assert "Devices appear to be online" in response_commands.llm_analysis.overall_assessment
        else:
            print(f"User Query (Commands & Report) - Unexpected response type: {type(response_commands)} - {getattr(response_commands, 'assistant_message', '')}")


        print("\\n--- Testing process_user_query (scenario: LLM provides a direct thought) ---")
        async def mock_llm_thought(*args, **kwargs):
            if kwargs.get('output_model') == LLMDataRequestAction:
                print("    (Mocking LLM to provide a direct thought...)")
                return LLMDataRequestAction(thought="For general slowness, often rebooting the local router and modem can help as a first step.")
            return await original_llm_handler_get_response(*args, **kwargs)

        manager.llm_handler.get_structured_response = mock_llm_thought
        user_query_thought = UserQueryInput(
            query="What are some general tips for slow home internet?",
            target_scope=TargetScope() # No specific devices
        )
        response_thought = await manager.process_user_query(user_query_thought)
        manager.llm_handler.get_structured_response = original_llm_handler_get_response # Restore
        
        if isinstance(response_thought, InterimChatResponse):
            print(f"User Query (Thought) - Assistant: {response_thought.assistant_message}")
            assert "rebooting the local router" in response_thought.assistant_message
        else:
            print(f"User Query (Thought) - Unexpected response type: {type(response_thought)}")
        
        logger.info("Note: LLM calls in main_test are active if API key is set and mocks are not used. pyATS interactions are stubbed.")
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