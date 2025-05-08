"""Pydantic data models for the Marvis module.

These models define the structure for inputs, outputs, and internal data handling,
including interactions with the LLM via Pydantic AI.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, FilePath, HttpUrl

# --- Input Data Models ---

class AlarmDetails(BaseModel):
    """Structured information about an alarm."""
    source: Optional[str] = Field(None, description="Source of the alarm (e.g., NMS, monitoring tool)")
    severity: Optional[str] = Field(None, description="Severity of the alarm (e.g., critical, major, minor)")
    affected_component: Optional[str] = Field(None, description="The component affected by the alarm")
    description: str = Field(..., description="Detailed description of the alarm")
    additional_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Any other relevant alarm attributes")

class TargetScope(BaseModel):
    """Defines the scope of the troubleshooting activity."""
    device_hostnames: Optional[List[str]] = Field(default_factory=list, description="List of specific device hostnames or IPs to target")
    market_or_region: Optional[str] = Field(None, description="Broader scope like a market or region")
    # Potentially other scoping parameters like device_group, site_id etc.

class ChatMessage(BaseModel):
    """Represents a single message in a chat history."""
    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message")

class FileUpload(BaseModel):
    """Represents an uploaded file, e.g., a log snippet."""
    filename: str = Field(..., description="Name of the uploaded file")
    content_type: Optional[str] = Field(None, description="MIME type of the file")
    # Content could be bytes or a path to a temporary file depending on handling
    # For simplicity, let's assume content is passed as string for now, or handled by client
    content: str = Field(..., description="Content of the file (e.g. log snippet as text)")

class UserQueryInput(BaseModel):
    """Input for a user-initiated troubleshooting query."""
    query: str = Field(..., description="User's natural language query")
    target_scope: TargetScope
    chat_history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Context from previous conversation turns")
    file_uploads: Optional[List[FileUpload]] = Field(default_factory=list, description="List of uploaded files for context")

# --- Intermediate Data Models (including for Pydantic AI) ---

class PyATSCommandRequest(BaseModel):
    """Specifies a single pyATS command to be executed on a set of devices."""
    command: str = Field(..., description="The pyATS show command to execute (e.g., 'show version')")
    devices: Optional[List[str]] = Field(default_factory=list, description="List of device hostnames to run this command on. If empty, may use overall target_scope.")
    # We could add a field for specific parser if needed, or derive from command.

class LLMDataRequestAction(BaseModel):
    """Pydantic model for the LLM to specify data gathering actions (FR5).

    The LLM will be prompted to return its response structured according to this model
    when it needs to request data from network devices.
    """
    thought: Optional[str] = Field(None, description="LLM's reasoning for requesting these actions.")
    pyats_commands: Optional[List[PyATSCommandRequest]] = Field(default_factory=list, description="List of pyATS commands to execute.")
    # Could extend with other data requests, e.g., specific API calls if module supported them.
    ask_user_clarification: Optional[str] = Field(None, description="If the LLM needs to ask the user a question for clarification.")

class PyATSCommandResult(BaseModel):
    """Structured result from a single pyATS command execution on a device."""
    device_hostname: str
    command: str
    raw_output: Optional[str] = None
    parsed_output: Optional[Union[Dict[str, Any], List[Any], str]] = None # Genie parsers typically return dicts/lists
    error: Optional[str] = None # If command execution or parsing failed

class ConnectivityTestResult(BaseModel):
    """Result of basic connectivity tests (ping, DNS)."""
    test_type: Literal["ping", "dns_resolution"]
    target: str
    success: bool
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="E.g., latency for ping, resolved IPs for DNS")

class LLMAnalysisResult(BaseModel):
    """Pydantic model for the LLM to provide its analysis, summary, and recommendations.

    The LLM will be prompted to return its final analysis structured according to this model.
    """
    overall_assessment: str = Field(..., description="The LLM's high-level assessment of the situation.")
    key_findings: List[str] = Field(default_factory=list, description="Bullet points of key findings from the data.")
    potential_root_causes: List[str] = Field(default_factory=list, description="Potential root causes identified by the LLM.")
    suggested_next_steps: List[str] = Field(default_factory=list, description="Suggested next troubleshooting steps for the engineer.")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="LLM's confidence in its assessment (0.0 to 1.0)")
    raw_reasoning_text: Optional[str] = Field(None, description="Full reasoning text from the LLM if needed for audit/details.")

# --- Output Data Models ---

class TroubleshootingReport(BaseModel):
    """Main troubleshooting report structure (FR13, FR14)."""
    request_type: Literal["alarm", "user_query"]
    original_request: Union[AlarmDetails, UserQueryInput]
    target_scope: TargetScope

    investigation_summary: Optional[str] = Field(None, description="A brief summary of the investigation performed.")
    devices_investigated: List[str] = Field(default_factory=list)
    connectivity_test_results: List[ConnectivityTestResult] = Field(default_factory=list)
    pyats_command_results: List[PyATSCommandResult] = Field(default_factory=list)

    llm_analysis: Optional[LLMAnalysisResult] = Field(None, description="Structured analysis from the LLM.")

    # For Markdown version, it would be a string generated from this structured data.
    # markdown_report: Optional[str] = None # This could be generated separately

class InterimChatResponse(BaseModel):
    """Interim response for interactive user queries."""
    assistant_message: str = Field(..., description="The LLM's message to the user (e.g., a question, an interim finding).")
    # Optionally, could include suggested quick actions or data requests if applicable
    # suggested_actions: Optional[List[str]] = None

class SupportedCapabilities(BaseModel):
    """Describes the data gathering capabilities of the module (FR5)."""
    supported_pyats_commands: List[str] = Field(..., description="List of pyATS show commands the module can execute.")
    # Could also include other capabilities, e.g., types of information it can parse/understand.


if __name__ == "__main__":
    # Example Usage (for testing and demonstration)

    # 1. Alarm Input Example
    alarm_input = AlarmDetails(
        source="SolarWinds",
        severity="Critical",
        affected_component="RouterA_Gig0/0/1",
        description="Interface Gig0/0/1 is down."
    )
    scope_input = TargetScope(device_hostnames=["RouterA", "SwitchB"])

    print("--- Example Alarm Input ---")
    print(alarm_input.model_dump_json(indent=2))
    print(scope_input.model_dump_json(indent=2))

    # 2. User Query Input Example
    user_query = UserQueryInput(
        query="Users in Building X are reporting slow internet. Can you check RouterC and AccessPointY?",
        target_scope=TargetScope(device_hostnames=["RouterC", "AccessPointY"], market_or_region="BuildingX"),
        chat_history=[
            ChatMessage(role="user", content="My internet is slow."),
            ChatMessage(role="assistant", content="Okay, which devices are you near?")
        ],
        file_uploads=[
            FileUpload(filename="speedtest.txt", content="Download: 10Mbps, Upload: 1Mbps")
        ]
    )
    print("\n--- Example User Query Input ---")
    print(user_query.model_dump_json(indent=2))

    # 3. LLM Data Request Action (LLM asks module to run commands)
    llm_data_req = LLMDataRequestAction(
        thought="The user mentioned interface down, I should check the interface status and logs on RouterA.",
        pyats_commands=[
            PyATSCommandRequest(command="show interfaces Gig0/0/1", devices=["RouterA"]),
            PyATSCommandRequest(command="show logging | include Gig0/0/1", devices=["RouterA"])
        ]
    )
    print("\n--- Example LLM Data Request Action ---")
    print(llm_data_req.model_dump_json(indent=2))

    # 4. PyATS Command Result Example
    cmd_res = PyATSCommandResult(
        device_hostname="RouterA",
        command="show version",
        parsed_output={"version": {"version_short": "16.9"}},
        raw_output="... some raw output ..."
    )
    print("\n--- Example PyATS Command Result ---")
    print(cmd_res.model_dump_json(indent=2))

    # 5. LLM Analysis Result Example
    llm_analysis_ex = LLMAnalysisResult(
        overall_assessment="Interface Gig0/0/1 on RouterA is administratively down.",
        key_findings=["Interface Gig0/0/1 status is 'admin down'", "No errors on the interface counter"],
        potential_root_causes=["Interface was manually shut down.", "Configuration error."],
        suggested_next_steps=["Verify if the interface should be up.", "Issue 'no shutdown' on the interface if appropriate."],
        confidence_score=0.9
    )
    print("\n--- Example LLM Analysis Result ---")
    print(llm_analysis_ex.model_dump_json(indent=2))

    # 6. Troubleshooting Report Example
    report = TroubleshootingReport(
        request_type="alarm",
        original_request=alarm_input,
        target_scope=scope_input,
        investigation_summary="Checked RouterA based on interface down alarm.",
        devices_investigated=["RouterA"],
        pyats_command_results=[cmd_res],
        llm_analysis=llm_analysis_ex
    )
    print("\n--- Example Troubleshooting Report ---")
    print(report.model_dump_json(indent=2))

    # 7. Supported Capabilities Example
    caps = SupportedCapabilities(
        supported_pyats_commands=["show version", "show ip interface brief", "show run interface <interface>"]
    )
    print("\n--- Example Supported Capabilities ---")
    print(caps.model_dump_json(indent=2))
