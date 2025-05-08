# Requirements Document: LLM-Powered Troubleshooting Module (v3.1 - Pydantic AI)

## 0. Revision History

| Version | Date       | Author(s)       | Summary of Changes                                                                                                                               |
|---------|------------|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| 3.0     | (Initial Date) | (Original Author) | Initial draft based on Pydantic AI integration.                                                                                                    |
| 3.1     | 2025-05-06 | AI Assistant    | Added Revision History, References, Verification sections. Expanded Data Requirements and Deployment Considerations. Added NFRs for Scalability and Availability. |

## 1. Introduction

### 1.1. Purpose

This document outlines the requirements for a Python module designed to assist in network troubleshooting. The module will leverage Large Language Models (LLMs) through Pydantic AI and the pyATS Genie library to interact with Cisco network devices, analyze data, and generate insightful reports.

### 1.2. Scope

The module will provide core logic for:

* Managing interactions with various LLMs using Pydantic AI, which in turn utilizes the respective LLM provider SDKs.
* Orchestrating the troubleshooting workflow, including prompting LLMs and interpreting their structured responses (parsed by Pydantic AI) to guide data collection.
* Connecting to Cisco devices and executing read-only commands using pyATS Genie, as directed by the module's orchestration logic (which is informed by the structured LLM output).
* Processing collected data from pyATS and LLM responses.
* Generating troubleshooting reports.
* Supporting both alarm-triggered and interactive user-initiated troubleshooting scenarios.

The module is intended to be a backend component, providing an API for various frontends/clients such as an MCP server, FastAPI web services, command-line interfaces (CLIs), and PySide6/Qt desktop applications. This document does **not** cover the development of these client applications, only the core Python module.

### 1.3. Target Audience

The primary audience for this document includes:

* Software developers building and maintaining the module.
* Developers integrating this module into client applications (MCP, FastAPI, CLI, GUI).
* Project managers overseeing the development.

## 2. Overall Description

### 2.1. Product Perspective

This module will serve as an intelligent backend for network troubleshooting applications. It aims to automate the initial data gathering and analysis phase of troubleshooting, providing engineers with a summarized report and potential root causes or solutions. It is not intended to perform automated remediation actions in its initial version (read-only).

### 2.2. Product Functions (High-Level)

* Accepts troubleshooting requests (alarm-based or user queries).
* Orchestrates LLM interactions for analysis using Pydantic AI, and guides data gathering based on structured LLM outputs.
* Utilizes pyATS Genie to collect data from Cisco network devices as directed by the module's internal logic (informed by structured LLM responses).
* Generates comprehensive troubleshooting reports.
* Provides a clear Python API for integration.

### 2.3. User Characteristics

The end-users of this module are Python developers who will integrate its functionalities into larger systems or client applications. They are expected to have experience with Python development and basic networking concepts.

### 2.4. Constraints

* **Programming Language:** Python (version 3.8 or higher).
* **Core Libraries:** pyATS Genie (for Cisco device interaction), Pydantic AI, and underlying LLM provider SDKs (e.g., OpenAI SDK, Google Generative AI SDK) as utilized by Pydantic AI.
* **Initial Device Interaction:** Read-only operations on Cisco devices. No configuration changes.
* **LLM Agnosticism:** While specific LLMs (e.g., Gemini, OpenAI models) will be targeted, the design should facilitate adding support for other models compatible with Pydantic AI.
* **Environment:** The module should be runnable in various environments where Python is supported, including servers and desktop machines.

### 2.5. Assumptions and Dependencies

* Access to LLM APIs (e.g., OpenAI, Google AI Studio) and valid API keys are required.
* Network connectivity to target Cisco devices from the environment where the module runs.
* Proper credentials and pyATS testbed configurations for accessing Cisco devices.
* Client applications are responsible for user authentication and managing user sessions.

## 3. Specific Requirements

### 3.1. Interface Requirements

#### 3.1.1. Programmatic Interface (Module API)

The module shall expose a well-defined Python API. Key components of this API include:

* **`TroubleshootingManager` Class:**
  * **Initialization (`__init__`)**:
    * Accepts configuration for LLM interaction via Pydantic AI (e.g., Pydantic AI compatible LLM model/client instance, API key, parameters like temperature).
    * Accepts configuration for pyATS (e.g., path to testbed file or connection parameters).
    * Accepts configuration for optional features (e.g., enable basic connectivity tests on failure).
    * Initializes necessary clients (e.g., Pydantic AI LLM client, pyATS Genie loader).
  * **`process_alarm(alarm_details: dict, target_scope: dict) -> dict`**:
    * Input: `alarm_details` (structured information about the alarm), `target_scope` (e.g., market, specific devices).
    * Output: A dictionary containing the troubleshooting report (e.g., in JSON or Markdown format).
    * Orchestrates LLM interaction (via Pydantic AI) and pyATS usage based on alarm context.
  * **`process_user_query(query: str, target_scope: dict, chat_history: list = None, file_uploads: list = None) -> dict`**:
    * Input: `query` (user's natural language query), `target_scope`, optional `chat_history` for context, optional `file_uploads` (e.g., log snippets).
    * Output: A dictionary containing the troubleshooting report or an interim chat response.
    * Orchestrates LLM interaction (via Pydantic AI) and pyATS usage based on user query and context.
  * **`get_supported_capabilities() -> dict`**:
    * Output: A dictionary describing the data gathering capabilities of the module (e.g., list of supported pyATS commands or information types the LLM can be instructed to request via structured output). This informs how the LLM can be prompted about what it can ask the module to do.
* **Configuration Management:**
  * Functions or mechanisms to load and manage sensitive configurations (API keys, device credentials) securely, preferably via environment variables or a configuration file system, integrated with Pydantic models for validation.

### 3.2. Functional Requirements

#### 3.2.1. LLM Interaction Management (Pydantic AI-based)

* **FR1: LLM Configuration & Selection:** The module must allow configuration of the LLM to be used. This should be managed via the `TroubleshootingManager` initialization using Pydantic AI, which interfaces with the underlying LLM SDKs. The module will specify the Pydantic model expected as the LLM's output.
* **FR2: Dynamic Prompt Formulation:** The module must dynamically formulate prompts for the LLM. These prompts will instruct the LLM on the task, provide context (alarm details, user queries, chat history, pyATS capabilities), and specify the Pydantic model structure for its response.
* **FR3: LLM Response Processing:** The module must use Pydantic AI to parse LLM responses into predefined Pydantic models. This structured output will represent identified intents for data gathering, analysis results, or other required information.
* **FR4: Conversation History Management:** For interactive user queries, the module (or the client via the module's API) should support managing conversation history to provide context to the LLM.
* **FR5: LLM-Directed Device Interaction (via pyATS, guided by Pydantic AI output):**
  * The module must enable the LLM to effectively request specific information from network devices by structuring its response according to a Pydantic model defined by the module. This model will specify fields for desired pyATS operations or data points.
  * The module's orchestration logic will interpret the structured output (the populated Pydantic model received from the LLM via Pydantic AI) and translate the specified operations/data requests into appropriate pyATS Genie command executions.
  * The module will manage the execution of these commands via pyATS Genie.
  * The structured results (or raw output) from pyATS Genie must be processed by the module and then can be supplied back to the LLM (again, via Pydantic AI with an expected structured response) for further analysis or summarization.
  * A predefined, extensible list of supported pyATS operations/commands (exposed via `get_supported_capabilities()`) should guide how the module prompts the LLM about what data it can request and the Pydantic model structure it should use in its response.

#### 3.2.2. Network Device Interaction (via pyATS Genie Interface)

* **FR6: Device Connection:** The module's pyATS interface must connect to specified Cisco devices using connection details from a pyATS testbed file or provided configuration.
* **FR7: Command Execution:** The module's pyATS interface must be able to execute a predefined and extensible set of read-only `show` commands on the target Cisco devices. The module's orchestration logic (informed by the structured LLM output) will determine which commands to run.
* **FR8: Output Parsing:** The module's pyATS interface must leverage Genie parsers to obtain structured data from command outputs. If a parser is not available, raw output should be returned.
* **FR9: Error Handling (Device Interaction):**
  * The module's pyATS interface must gracefully handle and report connection errors, command execution failures, or parsing issues back to the main orchestration logic.
  * **FR9.1: Optional Basic Connectivity Tests:**
    * If enabled via configuration, and a direct pyATS connection attempt to a device fails, the module shall trigger basic connectivity tests.
    * These tests should include:
      * ICMP Ping to the target device's IP address.
      * DNS resolution of the target device's hostname (if a hostname was used for connection).
    * The results of these connectivity tests (success/failure, latency, DNS resolution result) must be logged and can be included in the troubleshooting report or provided to the LLM for context.
    * This feature must be explicitly configurable (on/off).

#### 3.2.3. Data Processing and Analysis

* **FR10: Data Consolidation:** The module must consolidate data from various sources: alarm details, user input, pyATS command outputs, and structured LLM responses.
* **FR11: Data Preparation for LLM:** Data sent to the LLM (especially pyATS outputs) must be formatted or summarized by the module if necessary to fit within context window limits and be effectively used by the LLM. The structure of data provided to the LLM will be part of the prompt.
* **FR12: Feedback Loop (Placeholder for Future):** The system should be designed with future hooks in mind for implementing a feedback loop mechanism (e.g., user ratings of report usefulness) to fine-tune prompts or LLM behavior. This is not for V1 implementation but should be considered architecturally.

#### 3.2.4. Report Generation

* **FR13: Report Content:** The module must generate a troubleshooting report that includes:
  * Original alarm information or user query.
  * List of devices investigated and commands run (including results of any basic connectivity tests if performed).
  * Key findings from the collected device data.
  * The LLM's overall assessment, summary, and reasoning (derived from its structured responses).
  * Potential root causes or suggested next troubleshooting steps as identified by the LLM.
* **FR14: Report Format:** Reports should be available in a structured format, primarily JSON, to be easily consumable by client applications. A Markdown version for human readability is also desirable.
* **FR15: Clarity and Conciseness:** Reports should be clear, concise, and directly relevant to the troubleshooting request.

#### 3.2.5. Scenario Handling

* **FR16: Alarm-Triggered Workflow:**
  * Input: Structured alarm data (e.g., from an Solarwinds server via webhook to FastAPI).
  * Process: The module uses the alarm data to scope the investigation, prompts the LLM (via Pydantic AI) for an initial plan or data requirements (expecting a structured Pydantic model response), executes pyATS data gathering based on the LLM's structured output, potentially iterates with the LLM for further analysis, and generates a report.
* **FR17: Interactive User Query Workflow:**
  * Input: Natural language query from a user (e.g., via a CLI or PySide6 GUI). May include chat history and file uploads.
  * Process: The module engages the LLM (via Pydantic AI, expecting structured Pydantic model responses) in a conversational manner, interprets the LLM's structured output to trigger pyATS data gathering as needed, and provides interim responses or a final report.

### 3.3. Non-Functional Requirements

* **NFR1: Modularity:** The core troubleshooting logic (LLM interaction via Pydantic AI, pyATS interface, report generation) must be encapsulated within the module, independent of any specific client implementation (FastAPI, PySide6, CLI).
* **NFR2: Reusability:** Internal components of the module (e.g., pyATS interface, Pydantic AI interaction classes/functions) should be designed for reusability.
* **NFR3: Configurability:**
  * LLM API keys, model names, and parameters (used by Pydantic AI) must be configurable externally.
  * pyATS testbed information or device connection parameters must be configurable.
  * The set of allowed `show` commands for the pyATS interface should be configurable.
  * The optional basic connectivity tests (ping/DNS) must be configurable (enabled/disabled).
* **NFR4: Extensibility:**
  * The module should be designed to easily add support for new LLM models compatible with Pydantic AI.
  * Adding new `show` commands to the pyATS interface should be straightforward.
  * Extending the Pydantic models used for LLM interaction to support new capabilities should be manageable.
* **NFR5: Maintainability:**
  * The codebase must be well-documented (docstrings, comments for complex logic).
  * Adherence to Python best practices (PEP 8).
  * Comprehensive unit tests for critical components.
* **NFR6: Error Handling:** The module must implement robust error handling for:
  * LLM API errors (via Pydantic AI or underlying SDKs).
  * Pydantic AI parsing/validation errors.
  * Network connectivity issues to Cisco devices.
  * pyATS Genie errors.
  * Invalid input or configuration.
* **NFR7: Security:**
  * API keys and device credentials must not be hardcoded. Secure practices for managing secrets (e.g., environment variables, vault solutions) must be employed.
* **NFR8: Performance:**
  * Consider asynchronous operations where Pydantic AI and pyATS allow, to improve overall throughput for concurrent requests. Specific performance targets (e.g., average response time for typical scenarios) should be defined and tested.
* **NFR9: Scalability:**
  * The module should be designed to handle a reasonable increase in troubleshooting requests, primarily by being stateless where possible or by efficiently managing state for concurrent operations.
  * Considerations for scaling will depend on the deployment environment (e.g., number of worker processes if hosted in a web server).
* **NFR10: Availability/Reliability:**
  * The module should be robust and minimize downtime.
  * Graceful degradation of service if an LLM provider is temporarily unavailable (e.g., fallback to simpler logic or clear error reporting).

### 3.4. Data Requirements

* **Input Data:**
  * **Alarm-triggered Workflow:**
    * `alarm_details`: A dictionary containing structured information about the alarm (e.g., source, severity, affected component, description).
    * `target_scope`: A dictionary defining the scope of the troubleshooting (e.g., specific device hostnames/IPs, market, region).
  * **User-initiated Workflow:**
    * `query`: A string containing the user's natural language troubleshooting request.
    * `target_scope`: A dictionary defining the scope of the troubleshooting.
    * `chat_history` (optional): A list of previous turns in the conversation to provide context to the LLM. Each turn may include user input and system/LLM responses.
    * `file_uploads` (optional): A list of file-like objects or paths to files (e.g., log snippets, configuration excerpts) provided by the user for context.
* **Output Data:**
  * **Troubleshooting Report:** A dictionary (intended for JSON serialization) containing:
    * Original alarm information or user query.
    * List of devices investigated.
    * Commands executed on each device.
    * Results of basic connectivity tests (if performed).
    * Key findings from collected and analyzed data.
    * LLM's assessment, summary, and reasoning.
    * Potential root causes.
    * Suggested next troubleshooting steps.
  * **Markdown Report:** A human-readable version of the troubleshooting report in Markdown format.
  * **Interim Chat Response:** For interactive user queries, a dictionary containing the LLM's response, which might be a question for clarification, an interim finding, or a request for more information.
* **Intermediate Data:**
  * Parsed pyATS Output: Structured data (typically dictionaries or lists) obtained from Genie parsers.
  * LLM Prompts: Formatted text strings or structured input (e.g., list of messages) sent to the LLM API via Pydantic AI.
  * Raw LLM Responses: The direct text or JSON response received from the LLM before Pydantic AI parsing.
  * Structured LLM Output: Pydantic models populated by Pydantic AI from the LLM's responses, representing intents, analysis, or requested actions.
  * Connectivity Test Results: Structured data indicating success/failure, latency for pings, and resolution results for DNS lookups.
* **Configuration Data:**
  * **LLM Configuration:**
    * Pydantic AI compatible LLM client/model instance details (e.g., model name like `gpt-4o`, `gemini-pro`).
    * API key for the selected LLM provider.
    * LLM parameters (e.g., `temperature`, `max_tokens`).
  * **pyATS Configuration:**
    * Path to a pyATS testbed YAML file.
    * Alternatively, direct device connection parameters (hostname/IP, username, password/SSH keys, connection protocol like SSH/Telnet).
  * **Module Feature Configuration:**
    * Boolean flag to enable/disable optional basic connectivity tests upon device connection failure.
  * **Security Credentials:** Securely managed API keys and device credentials (not stored in code).
  * **Supported pyATS Commands:** A configurable list or mapping defining the `show` commands the module is permitted to execute, potentially with associated Genie parsers.

## 4. Tooling and Libraries

* **Python:** Version 3.8 or higher.
* **pyATS & Genie:** For Cisco device interaction and output parsing.
* **Pydantic AI:** For structuring interactions with LLMs and parsing their responses.
* **LLM Provider SDKs (e.g., OpenAI Python Library, Google Generative AI SDK):** As dependencies or utilized by Pydantic AI.
* **Pydantic:** (Core dependency of Pydantic AI) For data validation, settings management.
* **Standard library modules:** `subprocess` or a library like `pythonping` for ICMP pings; `socket` for DNS resolution (or a library like `dnspython`).
* **HTTPX or Requests:** (Likely used by Pydantic AI or LLM SDKs for API communication).
* **Logging:** Standard Python `logging` module.
* **Testing Framework:** `pytest` or `unittest`.
* **Configuration Management:** `python-dotenv` or similar for managing environment variables; Pydantic's `BaseSettings` for loading configurations.

## 5. Deployment Considerations

* **Python Environment:**
  * The module should be deployed within a dedicated Python virtual environment (e.g., using `venv` or `conda`) to manage dependencies and avoid conflicts.
  * A `requirements.txt` or `pyproject.toml` file must list all necessary dependencies and their versions.
* **Network Access:**
  * The host environment running the module must have network connectivity to:
    * The target LLM provider's API endpoints (e.g., OpenAI, Google Cloud).
    * The Cisco network devices that need to be troubleshot (e.g., via SSH, Telnet). This may involve firewall rule configurations.
* **Credentials Management:**
  * API keys for LLM services and credentials for network devices must be managed securely.
  * Recommended methods include environment variables, dedicated secrets management tools (e.g., HashiCorp Vault, AWS Secrets Manager), or encrypted configuration files, accessible at runtime. Avoid hardcoding credentials.
* **Resource Requirements:**
  * **CPU/Memory:** The module itself is likely to be lightweight, but interactions with LLMs and pyATS (especially parsing large outputs) can be resource-intensive. Sufficient CPU and memory should be allocated to the host environment. Specific requirements should be determined through testing.
  * **Disk Space:** Primarily for logs and any temporary storage of data.
  * **Network Bandwidth:** Sufficient bandwidth is needed for API calls to LLMs and data transfer from network devices.
* **Logging and Monitoring:**
  * The module should produce structured logs for operational monitoring, debugging, and auditing purposes.
  * Integration with centralized logging systems (e.g., ELK stack, Graylog) is recommended.
  * Key metrics (e.g., request rates, error rates, LLM interaction times, device interaction times) should be exposed for monitoring.
* **Operating System:** The module should be compatible with common server operating systems where Python is supported (e.g., Linux distributions, Windows Server).
* **Scalability Strategy:** If deployed as part of a larger service (e.g., a FastAPI application), standard web application scaling techniques (e.g., load balancers, multiple worker instances) can be applied to the hosting service. The module itself should aim to be stateless or manage state efficiently to support such scaling.

## 6. Glossary

* **LLM:** Large Language Model.
* **pyATS:** Python Automated Test System.
* **Genie:** A library within pyATS that provides parsers and an object-oriented model for network device configurations and operational states.
* **Pydantic AI:** A Python library for building AI applications with structured data interaction with LLMs, built on Pydantic.
* **SDK:** Software Development Kit.
* **MCP:** Management and Control Plane.
* **API:** Application Programming Interface.
* **CLI:** Command-Line Interface.
* **GUI:** Graphical User Interface.
* **ICMP:** Internet Control Message Protocol.
* **DNS:** Domain Name System.
* **JSON:** JavaScript Object Notation.
* **YAML:** YAML Ain't Markup Language.

## 7. Verification

The successful implementation of the module will be verified through a combination of methods:

* **V1: Unit Testing:** Each class, method, and function within the module will be accompanied by unit tests using a framework like `pytest` or `unittest`. This includes testing:
  * Logic for `TroubleshootingManager` methods.
  * Prompt formulation logic.
  * Pydantic model validation for LLM responses.
  * pyATS interface functions (mocking device interactions).
  * Data processing and report generation components.
  * Configuration loading and handling.
  * Error handling mechanisms.
* **V2: Integration Testing:**
  * Testing the interaction between the Pydantic AI layer and mock LLM services.
  * Testing the interaction between the module's core logic and a mock pyATS/Genie interface.
  * Verifying the end-to-end flow for `process_alarm` and `process_user_query` scenarios using mocked external dependencies.
* **V3: End-to-End (E2E) Testing:**
  * Testing the module with actual LLM APIs (in a controlled/sandboxed environment if possible, or using development-tier API access).
  * Testing connectivity and command execution against real or lab Cisco devices using pyATS.
  * Validating the content and format of generated reports against expected outcomes for defined test scenarios.
* **V4: Code Review:** All code contributions will undergo peer review to ensure adherence to coding standards, best practices, and requirement fulfillment.
* **V5: API Contract Verification:** Client application developers (or a representative QA function) will verify that the module's API (as defined in 3.1.1) meets their integration needs and behaves as documented.
* **V6: Functional Verification:** Testing all functional requirements (FR1-FR17) to ensure they are met. This involves creating test cases that cover various inputs, conditions, and expected outputs.
* **V7: Non-Functional Requirement Verification:**
  * **Performance:** Basic performance benchmarks for key operations (e.g., time taken for a typical troubleshooting session).
  * **Configurability:** Verifying that all specified configuration options work as intended.
  * **Error Handling:** Testing various failure scenarios (LLM API down, device unreachable, invalid input) to ensure graceful handling and informative error messages.
  * **Security:** Verifying that sensitive data is not hardcoded and that configuration for secure management is present.
* **V8: Documentation Review:** Ensuring all public APIs and complex internal logic are adequately documented.

## 8. References

* **Python:** [https://www.python.org/doc/](https://www.python.org/doc/)
* **Pydantic:** [https://docs.pydantic.dev/](https://docs.pydantic.dev/)
* **Pydantic AI:** (Link to Pydantic AI documentation, e.g., on GitHub or its official site)
* **pyATS & Genie:** [https://developer.cisco.com/pyats/](https://developer.cisco.com/pyats/)
* **OpenAI API (Example LLM Provider):** [https://platform.openai.com/docs](https://platform.openai.com/docs)
* **Google Generative AI SDK (Example LLM Provider):** [https://ai.google.dev/docs](https://ai.google.dev/docs)
* **PEP 8 -- Style Guide for Python Code:** [https://www.python.org/dev/peps/pep-0008/](https://www.python.org/dev/peps/pep-0008/)
