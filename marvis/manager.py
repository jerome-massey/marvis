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
            # System prompt and capabilities prompt sections can be customized in llm_handler.py
            # or passed via settings if more dynamic configuration is needed here.
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
                # This will be replaced by a more robust call that aggregates results.
                all_commands_to_run_on_devices: Dict[str, List[str]] = {} # device_name -> list of commands
                
                for cmd_req in llm_data_request.pyats_commands:
                    devices_for_this_command = cmd_req.devices or target_scope.device_hostnames or []
                    if not devices_for_this_command:
                        logger.warning(f"No target devices specified by LLM for command '{cmd_req.command}', skipping.")
                        continue
                    for device_name in devices_for_this_command:
                        if device_name not in all_commands_to_run_on_devices:
                            all_commands_to_run_on_devices[device_name] = []
                        # Ensure no duplicate commands for the same device from this initial request
                        if cmd_req.command not in all_commands_to_run_on_devices[device_name]:
                             all_commands_to_run_on_devices[device_name].append(cmd_req.command)

                # Execute commands device by device (or command by command, depending on PyATSHandler's design)
                # Current PyATSHandler executes one command on multiple devices.
                # We might need to iterate through unique commands and call it,
                # or enhance PyATSHandler to take a list of commands for a list of devices.
                # For now, let's iterate through commands suggested by LLM and run each on its target devices.

                unique_commands_from_llm = list(set(cmd_req.command for cmd_req in llm_data_request.pyats_commands if cmd_req.command))

                for command_str in unique_commands_from_llm:
                    # Determine which devices this specific command needs to run on based on LLM's request
                    devices_for_current_command = []
                    for cmd_req in llm_data_request.pyats_commands:
                        if cmd_req.command == command_str:
                            devices_for_current_command.extend(cmd_req.devices or target_scope.device_hostnames or [])
                    
                    # Remove duplicates while preserving order (though order might not be critical here)
                    unique_devices_for_command = sorted(list(set(d for d in devices_for_current_command if d)))


                    if not unique_devices_for_command:
                        logger.warning(f"No target devices ultimately resolved for command '{command_str}', skipping.")
                        continue
                    
                    logger.info(f"Executing command '{command_str}' on devices: {unique_devices_for_command} via PyATSHandler.")
                    results, conn_tests = await self.pyats_handler.execute_command_on_devices(
                        device_names=unique_devices_for_command,
                        command_to_execute=command_str
                    )
                    collected_pyats_results.extend(results)
                    connectivity_test_results_agg.extend(conn_tests)
                    # Log summary of this specific command execution
                    for res in results:
                        if res.error:
                            logger.warning(f"Error executing '{res.command}' on {res.device_hostname}: {res.error}")
                        else:
                            logger.info(f"Successfully executed '{res.command}' on {res.device_hostname}.")
                    for ct_res in conn_tests:
                        logger.info(f"Connectivity test {ct_res.test_type} for {ct_res.target}: Success={ct_res.success}")


            if collected_pyats_results:
                investigation_summary += f" Executed {len(unique_commands_from_llm)} unique command(s) across relevant devices."
            else:
                investigation_summary += " No pyATS commands were executed based on LLM's request or device availability."
            
            # Remove previous stubbed code
            # logger.warning(f"PyATS command execution for '{cmd_req.command}' is stubbed.")
            # # Add dummy results for now to allow flow to continue
            # for device_name in devices_to_run_on:
            #     collected_pyats_results.append(PyATSCommandResult(
            #         device_hostname=device_name,
            #         command=cmd_req.command,
            #         raw_output=f"Stubbed output for {cmd_req.command} on {device_name}",
            #         error="Stubbed execution - PyATSHandler not fully integrated."
            #     ))
            # investigation_summary += f" Attempted to run {len(llm_data_request.pyats_commands)} types of commands."
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
                    analysis_context_parts.append(f"    Raw Output: {res.raw_output[:200]}...") # Truncate for brevity
                if res.error:
                    analysis_context_parts.append(f"    Error: {res.error}")
            
            if connectivity_test_results_agg:
                analysis_context_parts.append("\\nConnectivity Test Results:")
                for conn_test in connectivity_test_results_agg:
                    details_str = f"Target: {conn_test.target}, Success: {conn_test.success}"
                    if conn_test.details:
                        details_str += f", Details: {str(conn_test.details)[:100]}..."
                    analysis_context_parts.append(f"  - {conn_test.test_type}: {details_str}")
            
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
                    # No pyats_capabilities_summary needed here as we are providing data, not asking for commands
                )
                logger.info(f"LLM analysis received. Overall assessment: {llm_analysis_result.overall_assessment[:100]}...")
                investigation_summary += f" LLM analysis completed. Assessment: {llm_analysis_result.overall_assessment[:50]}..."

            except Exception as e:
                logger.error(f"Error during LLM analysis phase: {e}", exc_info=True)
                investigation_summary += f" Error during LLM analysis: {e}."
                # Fallback: create a simple LLMAnalysisResult if the LLM call fails
                llm_analysis_result = LLMAnalysisResult(
                    overall_assessment="LLM analysis failed. Review collected data manually.",
                    key_findings=["LLM analysis could not be performed due to an error."],
                    potential_root_causes=["Error in LLM communication or response processing."],
                    suggested_next_steps=["Check logs for LLMHandler errors.", "Review raw pyATS data if collected."]
                )
        elif not llm_data_request or not llm_data_request.pyats_commands and not llm_data_request.ask_user_clarification : # If no data and no clarification, make a simple assessment
             try:
                logger.info("No pyATS data collected and no clarification requested by LLM. Generating simple assessment.")
                simple_assessment_query = (
                    "Based on the initial alarm details only, provide a very brief initial assessment "
                    "and suggest generic next steps for investigation, as no specific device data "
                    "was requested or collected."
                )
                llm_analysis_result = await self.llm_handler.get_structured_response(
                    user_query=simple_assessment_query,
                    output_model=LLMAnalysisResult,
                    current_context=initial_context_str
                )
                investigation_summary += " LLM provided a general assessment based on alarm details only."
                logger.info(f"LLM simple assessment: {llm_analysis_result.overall_assessment[:100]}...")
             except Exception as e:
                logger.error(f"Error during simple LLM assessment: {e}", exc_info=True)
                investigation_summary += f" Error during simple LLM assessment: {e}."
                llm_analysis_result = LLMAnalysisResult(
                    overall_assessment="Initial LLM assessment failed. Alarm details may be insufficient or LLM error.",
                    key_findings=["No device data was collected.", "LLM could not provide an initial assessment."],
                    potential_root_causes=["Insufficient information from alarm.", "LLM communication error."],
                    suggested_next_steps=["Manually review alarm details.", "Consider direct device investigation."]
                )
        else: # Handles cases like only clarification was asked, or llm_data_request itself failed.
            logger.info("No pyATS data collected. LLM analysis will be based on initial alarm and any clarifications.")
            if llm_data_request and llm_data_request.ask_user_clarification:
                clarification_text = f"LLM requested clarification: {llm_data_request.ask_user_clarification}"
                investigation_summary += f" {clarification_text}"
                llm_analysis_result = LLMAnalysisResult(
                    overall_assessment=f"Further action pending user clarification. {clarification_text}",
                    key_findings=[clarification_text],
                    potential_root_causes=["Information insufficient for automated diagnosis without clarification."],
                    suggested_next_steps=["Provide the requested clarification to proceed."]
                )
            else: # llm_data_request might have failed before even asking for clarification or commands
                 llm_analysis_result = LLMAnalysisResult(
                    overall_assessment="Initial LLM interaction for data gathering failed or yielded no actions. Cannot proceed with data-driven analysis.",
                    key_findings=["Failed to determine data gathering steps via LLM."],
                    potential_root_causes=["Problem with LLM prompt/response or initial alarm data interpretation."],
                    suggested_next_steps=["Review manager logs for errors in the first LLM call.", "Check alarm details for clarity."]
                )


        # 4. Build and return the report (FR13, FR14)
        if not self.report_builder:
            logger.error("ReportBuilder is not initialized. Cannot generate a report.")
            # Return a minimal report or raise an error
            # For now, creating a basic TroubleshootingReport with available data
            return TroubleshootingReport(
                request_type="alarm",
                original_request=alarm_details,
                target_scope=target_scope,
                investigation_summary=investigation_summary + " ReportBuilder failed to initialize.",
                devices_investigated=list(set(res.device_hostname for res in collected_pyats_results)),
                connectivity_test_results=connectivity_test_results_agg,
                pyats_command_results=collected_pyats_results,
                llm_analysis=llm_analysis_result
            )

        final_report = self.report_builder.build_report(
            request_type="alarm",
            original_request=alarm_details,
            target_scope=target_scope,
            investigation_summary=investigation_summary,
            devices_investigated=list(set(res.device_hostname for res in collected_pyats_results)), # Unique list
            pyats_results=collected_pyats_results,
            connectivity_tests=connectivity_test_results_agg,
            llm_analysis=llm_analysis_result,
        )
        logger.info(f"Alarm processing complete for: '{alarm_details.description[:50]}...'. Report generated.")
        return final_report

    async def process_user_query(
        self, query: str, target_scope: TargetScope, 
        chat_history: Optional[List[Dict[str, str]]] = None, # Conforms to LLMHandler expected input
        file_uploads: Optional[List[Dict[str, str]]] = None # Simplified for now
    ) -> Union[TroubleshootingReport, InterimChatResponse]: # FR17
        """
        Processes an interactive user query. (FR17)

        Orchestrates LLM interaction (via Pydantic AI) and pyATS usage
        based on user query and context. Can return an interim chat response
        or a full troubleshooting report.

        Args:
            query: User's natural language query.
            target_scope: Defines the scope of the troubleshooting.
            chat_history: Conversation history.
            file_uploads: Uploaded files for context (e.g., log snippets).
                          Each dict: {"filename": "...", "content": "..."}

        Returns:
            Either a TroubleshootingReport or an InterimChatResponse.
        """
        logger.info(f"Processing user query: '{query[:100]}...' for target: {target_scope.model_dump_json(exclude_none=True)}")

        # This is a simplified initial structure for process_user_query.
        # A full implementation would involve a loop for conversation,
        # state management, and deciding when to finalize a report vs. continue chatting.

        # 1. Prepare context for LLM
        full_query_context_parts = [f"User Query: {query}"]
        if target_scope.device_hostnames:
            full_query_context_parts.append(f"Target Devices: {', '.join(target_scope.device_hostnames)}")
        if target_scope.market_or_region:
            full_query_context_parts.append(f"Target Scope: {target_scope.market_or_region}")

        if file_uploads:
            full_query_context_parts.append("\\nUploaded Files Context:")
            for upload in file_uploads:
                full_query_context_parts.append(f"  Filename: {upload.get('filename', 'N/A')}")
                full_query_context_parts.append(f"  Content Snippet: {str(upload.get('content', ''))[:200]}...") # Truncate

        current_context_str = "\\n".join(full_query_context_parts)
        
        capabilities_summary = f"Supported pyATS commands include: {', '.join(self.settings.allowed_pyats_commands)}. " \\
                               "You can also ask for user clarification."

        # 2. Interact with LLM: Understand query, request data, or ask clarification
        # For user queries, the LLM might respond with a direct answer, a request for pyATS commands,
        # or a clarifying question. We'll use LLMDataRequestAction for now, but might need a more
        # general LLM response model for chat.
        try:
            logger.debug("Attempting LLM call for user query understanding and action planning.")
            llm_response_action = await self.llm_handler.get_structured_response(
                user_query=query, # The user's latest query is the main prompt part
                output_model=LLMDataRequestAction, # Re-using this model for now
                current_context=current_context_str, # Provides combined context of query + files
                chat_history=chat_history, # Passes along the history
                pyats_capabilities_summary=capabilities_summary
            )
            logger.info(f"LLM response to user query: Thought: {llm_response_action.thought or 'N/A'}")

            # 3. Process LLM's response
            collected_pyats_results: List[PyATSCommandResult] = []
            connectivity_test_results_agg: List[ConnectivityTestResult] = []
            investigation_summary = f"Investigation based on user query: {query[:50]}..."

            if llm_response_action.pyats_commands and self.pyats_handler:
                logger.info(f"LLM requested {len(llm_response_action.pyats_commands)} pyATS command(s).")
                # Similar command execution logic as in process_alarm
                unique_commands_from_llm = list(set(cmd_req.command for cmd_req in llm_response_action.pyats_commands if cmd_req.command))
                for command_str in unique_commands_from_llm:
                    devices_for_current_command = []
                    for cmd_req in llm_response_action.pyats_commands:
                        if cmd_req.command == command_str:
                            devices_for_current_command.extend(cmd_req.devices or target_scope.device_hostnames or [])
                    unique_devices_for_command = sorted(list(set(d for d in devices_for_current_command if d)))

                    if not unique_devices_for_command:
                        logger.warning(f"No target devices for command '{command_str}' in user query flow, skipping.")
                        continue
                    
                    results, conn_tests = await self.pyats_handler.execute_command_on_devices(
                        device_names=unique_devices_for_command,
                        command_to_execute=command_str
                    )
                    collected_pyats_results.extend(results)
                    connectivity_test_results_agg.extend(conn_tests)
                investigation_summary += f" Executed {len(unique_commands_from_llm)} command(s)."

            elif llm_response_action.pyats_commands and not self.pyats_handler:
                logger.warning("PyATSHandler not available. Cannot execute LLM-requested commands for user query.")
                investigation_summary += " PyATSHandler not available, commands not executed."
                # Potentially return an interim response indicating this issue.
                return InterimChatResponse(
                    assistant_message="I identified some commands to run, but I'm currently unable to connect to network devices. Please check my configuration."
                )


            # 4. Second LLM interaction (if data was collected) or formulate response
            llm_analysis_result: Optional[LLMAnalysisResult] = None
            if collected_pyats_results:
                analysis_context_parts = [current_context_str, "\\nCollected pyATS Data:"]
                for res in collected_pyats_results:
                    analysis_context_parts.append(f"  Device: {res.device_hostname}, Command: {res.command}")
                    if res.parsed_output:
                        analysis_context_parts.append(f"    Parsed: {str(res.parsed_output)[:200]}...")
                    elif res.raw_output:
                        analysis_context_parts.append(f"    Raw Output: {res.raw_output[:200]}...")
                    if res.error:
                        analysis_context_parts.append(f"    Error: {res.error}")
                if connectivity_test_results_agg:
                    analysis_context_parts.append("\\nConnectivity Test Results:")
                    for conn_test in connectivity_test_results_agg:
                        details_str = f"Target: {conn_test.target}, Success: {conn_test.success}"
                        if conn_test.details:
                            details_str += f", Details: {str(conn_test.details)[:100]}..."
                        analysis_context_parts.append(f"  - {conn_test.test_type}: {details_str}")
                
                analysis_context_str_for_llm = "\\n".join(analysis_context_parts)
                analysis_llm_query = (
                    "Analyze the user's query, chat history, uploaded files (if any), and the collected device data. "
                    "Provide an overall assessment, key findings, potential root causes, and suggested next steps. "
                    "If the query seems fully addressed, provide a comprehensive answer. "
                    "If more information or steps are needed, you can also ask a clarifying question."
                )
                # For user queries, the response might be another question or a final analysis.
                # We might need a more flexible output model here, e.g., one that includes
                # both LLMAnalysisResult fields and an optional 'ask_user_clarification' field.
                # For now, we'll assume if data is collected, we aim for an LLMAnalysisResult.
                try:
                    llm_analysis_result = await self.llm_handler.get_structured_response(
                        user_query=analysis_llm_query, # This is more of an instruction now
                        output_model=LLMAnalysisResult, # Expecting a full analysis
                        current_context=analysis_context_str_for_llm, # Context includes original query + data
                        chat_history=chat_history
                    )
                    investigation_summary += f" LLM analysis of collected data completed."
                except Exception as e:
                    logger.error(f"Error during LLM analysis for user query: {e}", exc_info=True)
                    return InterimChatResponse(assistant_message=f"I encountered an error trying to analyze the collected data: {e}")

            # 5. Decide on response type: InterimChatResponse or TroubleshootingReport
            if llm_response_action.ask_user_clarification and not collected_pyats_results:
                # If LLM asked a question and didn't run commands, it's an interim response.
                logger.info(f"LLM is asking for clarification from user: {llm_response_action.ask_user_clarification}")
                return InterimChatResponse(assistant_message=llm_response_action.ask_user_clarification)
            
            if llm_analysis_result: # If we have an analysis (from data or direct query)
                # This implies a more "final" answer for the current turn.
                # In a true conversational flow, we'd need more logic to decide if it's THE final report.
                # For now, if analysis is produced, we generate a report.
                if not self.report_builder:
                    logger.error("ReportBuilder not initialized. Cannot generate report for user query.")
                    return InterimChatResponse(assistant_message="I have processed your query and have some findings, but I'm unable to generate a formatted report at the moment.")

                # Constructing UserQueryInput for the report
                original_request_for_report = UserQueryInput(
                    query=query,
                    target_scope=target_scope,
                    chat_history=[ChatMessage(**msg) for msg in chat_history] if chat_history else [],
                    file_uploads=[FileUpload(**up) for up in file_uploads] if file_uploads else []
                )

                final_report = self.report_builder.build_report(
                    request_type="user_query",
                    original_request=original_request_for_report,
                    target_scope=target_scope,
                    investigation_summary=investigation_summary,
                    devices_investigated=list(set(res.device_hostname for res in collected_pyats_results)),
                    pyats_results=collected_pyats_results,
                    connectivity_tests=connectivity_test_results_agg,
                    llm_analysis=llm_analysis_result,
                )
                logger.info(f"User query processing generated a full report. Query: '{query[:50]}...'")
                return final_report
            elif not llm_response_action.pyats_commands and not llm_response_action.ask_user_clarification:
                # LLM didn't ask for commands and didn't ask a question, but also didn't produce data for analysis.
                # This could be a direct answer from the LLM's knowledge.
                # The LLMDataRequestAction.thought might contain this answer.
                # This part needs refinement based on how Pydantic AI agent is used for direct Q&A.
                # For now, if 'thought' exists, return it as an interim response.
                direct_answer = llm_response_action.thought or "I've processed your query. Is there anything else I can help with?"
                logger.info(f"LLM provided a direct response/thought: {direct_answer[:100]}...")
                return InterimChatResponse(assistant_message=direct_answer)
            else:
                # Fallback or if only commands were issued but no subsequent analysis was triggered (should be rare)
                logger.warning("User query processing ended in an unexpected state. Defaulting to generic interim response.")
                return InterimChatResponse(assistant_message="I've processed your request. If commands were run, I'll analyze the data. If not, I might need more information or your query was general.")


    def get_supported_capabilities(self) -> SupportedCapabilities: # FR5 (Exposing capabilities)
        """
        Returns the data gathering capabilities of the module.
        This informs how the LLM can be prompted about what it can ask the module to do.
        """
        logger.debug("Fetching supported capabilities.")
        return SupportedCapabilities(
            supported_pyats_commands=list(self.settings.allowed_pyats_commands)
            # Future: Could add other capabilities, e.g., "can_analyze_syslogs_if_provided"
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