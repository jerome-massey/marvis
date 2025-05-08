"""
Builds troubleshooting reports in various formats for the Marvis module.

Generates troubleshooting reports in JSON and Markdown formats.
Complies with FR13, FR14, FR15.
"""

import logging
import markdown
from typing import Any, Dict, List, Literal, Optional, Union

from .data_models import (
    AlarmDetails,
    UserQueryInput,
    TargetScope,
    PyATSCommandResult,
    ConnectivityTestResult,
    LLMAnalysisResult,
    TroubleshootingReport,
)

logger = logging.getLogger(__name__)


class ReportBuilder:
    """
    Builds troubleshooting reports in various formats (JSON, Markdown).
    Complies with FR13, FR14, FR15.
    """

    def __init__(self):
        """Initializes the ReportBuilder."""
        logger.info("ReportBuilder initialized.")

    def _generate_markdown_report(self, report_data: TroubleshootingReport) -> str:
        """Generates a Markdown formatted report from the TroubleshootingReport object."""
        md_lines = []

        # Title
        md_lines.append(f"# Troubleshooting Report: {report_data.request_type.capitalize().replace('_', ' ')}")
        md_lines.append("---_---")

        # Original Request
        md_lines.append("## 1. Original Request")
        if isinstance(report_data.original_request, AlarmDetails):
            alarm = report_data.original_request
            md_lines.append(f"- **Type**: Alarm")
            md_lines.append(f"- **Source**: {alarm.source or 'N/A'}")
            md_lines.append(f"- **Severity**: {alarm.severity or 'N/A'}")
            md_lines.append(f"- **Affected Component**: {alarm.affected_component or 'N/A'}")
            md_lines.append(f"- **Description**: {alarm.description}")
            if alarm.additional_info:
                md_lines.append(f"- **Additional Info**:")
                for key, value in alarm.additional_info.items():
                    md_lines.append(f"  - {key}: {value}")
        elif isinstance(report_data.original_request, UserQueryInput):
            query_input = report_data.original_request
            md_lines.append(f"- **Type**: User Query")
            md_lines.append(f"- **Query**: {query_input.query}")
            if query_input.chat_history:
                md_lines.append(f"- **Chat History Snippet (last {len(query_input.chat_history)} turns)**:")
                for msg in query_input.chat_history[-5:]: # Show last 5 for brevity
                    md_lines.append(f"  - **{msg.role.capitalize()}**: {msg.content}")
            if query_input.file_uploads:
                md_lines.append(f"- **File Uploads**:")
                for f_upload in query_input.file_uploads:
                    md_lines.append(f"  - {f_upload.filename} (Content snippet: {f_upload.content[:100]}...)")
        md_lines.append("\n## 2. Target Scope")
        md_lines.append(f"- **Devices Specified**: {', '.join(report_data.target_scope.device_hostnames) if report_data.target_scope.device_hostnames else 'None Specified'}")
        md_lines.append(f"- **Market/Region**: {report_data.target_scope.market_or_region or 'N/A'}")

        # Investigation Summary
        md_lines.append("\n## 3. Investigation Summary")
        md_lines.append(report_data.investigation_summary or "No summary provided.")

        # Devices Investigated
        if report_data.devices_investigated:
            md_lines.append("\n## 4. Devices Investigated")
            md_lines.append(", ".join(report_data.devices_investigated))

        # Connectivity Tests
        if report_data.connectivity_test_results:
            md_lines.append("\n## 5. Connectivity Test Results")
            for test in report_data.connectivity_test_results:
                md_lines.append(f"- **Test Type**: {test.test_type.upper()}")
                md_lines.append(f"  - **Target**: {test.target}")
                md_lines.append(f"  - **Success**: {'Yes' if test.success else 'No'}")
                if test.details:
                    md_lines.append(f"  - **Details**:")
                    for key, value in test.details.items():
                        if value: # Only print if value is not None or empty
                            md_lines.append(f"    - {key.replace('_', ' ').capitalize()}: {value}")
            md_lines.append("")

        # pyATS Command Results
        if report_data.pyats_command_results:
            md_lines.append("## 6. pyATS Command Results")
            for result in report_data.pyats_command_results:
                md_lines.append(f"### 6.{report_data.pyats_command_results.index(result) + 1}. Device: {result.device_hostname} - Command: `{result.command}`")
                if result.error:
                    md_lines.append(f"- **Status**: Error")
                    md_lines.append(f"- **Error Message**: `{result.error}`")
                else:
                    md_lines.append(f"- **Status**: Success")
                
                if result.parsed_output:
                    md_lines.append(f"- **Parsed Output (Snippet)**:")
                    md_lines.append("```json")
                    # Basic pretty print for snippet, actual JSON can be complex
                    import json
                    try:
                        parsed_str = json.dumps(result.parsed_output, indent=2)
                        md_lines.append(parsed_str[:1000] + ("... (truncated)" if len(parsed_str) > 1000 else ""))
                    except TypeError: # Handle non-serializable data if any
                        md_lines.append(str(result.parsed_output)[:1000] + "... (truncated)")
                    md_lines.append("```")
                elif result.raw_output:
                    md_lines.append(f"- **Raw Output (Snippet)**:")
                    md_lines.append("```text")
                    md_lines.append(result.raw_output[:1000] + ("... (truncated)" if len(result.raw_output) > 1000 else ""))
                    md_lines.append("```")
                md_lines.append("") # Spacer

        # LLM Analysis
        if report_data.llm_analysis:
            llm_analysis = report_data.llm_analysis
            md_lines.append("## 7. LLM Analysis & Recommendations")
            md_lines.append(f"### Overall Assessment")
            md_lines.append(llm_analysis.overall_assessment)
            
            if llm_analysis.key_findings:
                md_lines.append(f"\n### Key Findings")
                for finding in llm_analysis.key_findings:
                    md_lines.append(f"- {finding}")
            
            if llm_analysis.potential_root_causes:
                md_lines.append(f"\n### Potential Root Causes")
                for cause in llm_analysis.potential_root_causes:
                    md_lines.append(f"- {cause}")
            
            if llm_analysis.suggested_next_steps:
                md_lines.append(f"\n### Suggested Next Steps")
                for step in llm_analysis.suggested_next_steps:
                    md_lines.append(f"- {step}")
            
            if llm_analysis.confidence_score is not None:
                md_lines.append(f"\n- **Confidence Score**: {llm_analysis.confidence_score*100:.1f}%")
            if llm_analysis.raw_reasoning_text:
                md_lines.append(f"\n### LLM Raw Reasoning (Details)")
                md_lines.append("```text")
                md_lines.append(llm_analysis.raw_reasoning_text)
                md_lines.append("```")
        else:
            md_lines.append("## 7. LLM Analysis & Recommendations")
            md_lines.append("No LLM analysis was performed or it was not successful.")

        return "\n".join(md_lines)

    def build_report(
        self,
        request_type: Literal["alarm", "user_query"],
        original_request: Union[AlarmDetails, UserQueryInput],
        target_scope: TargetScope,
        investigation_summary: Optional[str] = None,
        devices_investigated: Optional[List[str]] = None,
        pyats_results: Optional[List[PyATSCommandResult]] = None,
        connectivity_tests: Optional[List[ConnectivityTestResult]] = None,
        llm_analysis: Optional[LLMAnalysisResult] = None,
    ) -> TroubleshootingReport:
        """
        Constructs a TroubleshootingReport object.
        The JSON representation is implicitly available via Pydantic's .model_dump_json().
        A Markdown version can be generated from this object.

        Args:
            request_type: Type of the original request.
            original_request: The alarm details or user query input.
            target_scope: The scope of the troubleshooting.
            investigation_summary: Summary of the investigation steps.
            devices_investigated: List of device hostnames that were investigated.
            pyats_results: List of results from pyATS command executions.
            connectivity_tests: List of results from basic connectivity tests.
            llm_analysis: Structured analysis from the LLM.

        Returns:
            A TroubleshootingReport object.
        """
        logger.info(f"Building report for {request_type} request.")

        report = TroubleshootingReport(
            request_type=request_type,
            original_request=original_request,
            target_scope=target_scope,
            investigation_summary=investigation_summary or "Investigation summary not provided.",
            devices_investigated=devices_investigated or [],
            pyats_command_results=pyats_results or [],
            connectivity_test_results=connectivity_tests or [],
            llm_analysis=llm_analysis,
        )
        logger.debug("TroubleshootingReport object created.")
        return report

    def get_markdown_from_report_obj(self, report_obj: TroubleshootingReport) -> str:
        """Generates and returns the Markdown string from a TroubleshootingReport object."""
        logger.info("Generating Markdown from TroubleshootingReport object.")
        md_string = self._generate_markdown_report(report_obj)
        # Optionally, convert Markdown string to HTML if needed by a client
        # html_output = markdown.markdown(md_string)
        return md_string


if __name__ == "__main__":
    # Example Usage (for testing and demonstration)
    from datetime import datetime

    # 1. Create dummy data similar to what TroubleshootingManager would produce
    example_alarm = AlarmDetails(
        source="TestNMS",
        severity="Major",
        affected_component="core-router-01/Gig0/1",
        description="High interface errors on Gig0/1",
        additional_info={"ticket_id": "INC12345"}
    )
    example_scope = TargetScope(device_hostnames=["core-router-01", "dist-switch-02"])

    example_pyats_res1 = PyATSCommandResult(
        device_hostname="core-router-01",
        command="show interface Gig0/1",
        raw_output="GigabitEthernet0/1 is up, line protocol is up... Errors: 1023 input, 0 output...",
        parsed_output={
            "GigabitEthernet0/1": {
                "status": "up",
                "protocol": "up",
                "counters": {"in_errors": 1023, "out_errors": 0}
            }
        }
    )
    example_pyats_res2 = PyATSCommandResult(
        device_hostname="core-router-01",
        command="show logging | i Gig0/1",
        raw_output="No relevant logs found for Gig0/1 recently.",
        error=None # No error in execution, but output might be empty
    )
    example_pyats_res_error = PyATSCommandResult(
        device_hostname="dist-switch-02",
        command="show version",
        error="Connection timed out to device dist-switch-02"
    )

    example_conn_test1 = ConnectivityTestResult(
        test_type="ping",
        target="dist-switch-02",
        success=False,
        details={"output": "Request timed out."}
    )

    example_llm_analysis = LLMAnalysisResult(
        overall_assessment="Interface Gig0/1 on core-router-01 is experiencing input errors. This likely indicates a Layer 1 or Layer 2 issue on that segment.",
        key_findings=[
            "core-router-01 interface Gig0/1 has 1023 input errors.",
            "Line protocol is up, suggesting basic connectivity is there.",
            "No specific error logs found recently for this interface on core-router-01.",
            "dist-switch-02 was unreachable for further checks."
        ],
        potential_root_causes=[
            "Bad cable or SFP on core-router-01 Gig0/1 or connected device.",
            "Duplex mismatch with the connected device.",
            "Faulty port on core-router-01 or the connected device."
        ],
        suggested_next_steps=[
            "Check physical cabling for interface Gig0/1 on core-router-01.",
            "Replace SFP on core-router-01 Gig0/1 if errors persist.",
            "Verify interface statistics on the device connected to core-router-01 Gig0/1.",
            "Investigate connectivity issues with dist-switch-02 separately."
        ],
        confidence_score=0.85,
        raw_reasoning_text="The high input error count is a strong indicator of a physical layer problem. Since the protocol is up, it's less likely to be a complete link failure but rather a quality issue. The lack of logs means it might be a silent hardware fault or a problem on the far end. The inability to reach dist-switch-02 hampers full diagnosis of that path."
    )

    # 2. Initialize ReportBuilder
    builder = ReportBuilder()

    # 3. Build the TroubleshootingReport object
    report_object = builder.build_report(
        request_type="alarm",
        original_request=example_alarm,
        target_scope=example_scope,
        investigation_summary="Initial automated investigation based on alarm. Checked interface stats and logs on core-router-01. Attempted to check dist-switch-02.",
        devices_investigated=["core-router-01", "dist-switch-02"],
        pyats_results=[example_pyats_res1, example_pyats_res2, example_pyats_res_error],
        connectivity_tests=[example_conn_test1],
        llm_analysis=example_llm_analysis
    )

    # 4. Get JSON output (Pydantic handles this automatically)
    json_report_str = report_object.model_dump_json(indent=2)
    print("--- JSON Report ---")
    print(json_report_str)

    # 5. Get Markdown output
    markdown_report_str = builder.get_markdown_from_report_obj(report_object)
    print("\n\n--- Markdown Report ---")
    print(markdown_report_str)

    # Save Markdown to a file for review
    md_filename = f"troubleshooting_report_example_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(markdown_report_str)
    print(f"\nMarkdown report saved to: {md_filename}")

    # Example for a user query report (simpler, without pyATS data)
    example_user_query = UserQueryInput(
        query="Users in Sales department cannot access CRM.",
        target_scope=TargetScope(device_hostnames=["sales-firewall", "crm-server-internal-lb"]),
        chat_history=[
            {"role": "user", "content": "CRM is down for Sales"},
            {"role": "assistant", "content": "Okay, I will check the sales-firewall and CRM load balancer."}
        ]
    )
    example_llm_analysis_user = LLMAnalysisResult(
        overall_assessment="Issue likely related to sales-firewall or CRM load balancer based on user query. No device data collected in this example.",
        key_findings=["User query indicates CRM access issue for Sales department."],
        potential_root_causes=["Firewall policy blocking access.", "CRM LB issue.", "CRM application server issue."],
        suggested_next_steps=["Check firewall logs on sales-firewall for blocks related to CRM IPs/ports.", "Verify status of CRM LB and its backend servers."]
    )
    user_query_report_obj = builder.build_report(
        request_type="user_query",
        original_request=example_user_query,
        target_scope=example_user_query.target_scope,
        investigation_summary="Initial assessment based on user query. No device commands executed in this example.",
        llm_analysis=example_llm_analysis_user
    )
    markdown_user_query_report_str = builder.get_markdown_from_report_obj(user_query_report_obj)
    print("\n\n--- Markdown User Query Report (No pyATS data) ---")
    print(markdown_user_query_report_str)
    md_user_filename = f"user_query_report_example_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_user_filename, "w", encoding="utf-8") as f:
        f.write(markdown_user_query_report_str)
    print(f"\nUser query Markdown report saved to: {md_user_filename}")