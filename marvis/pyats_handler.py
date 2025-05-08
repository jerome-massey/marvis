"""
Handles pyATS device connections and command execution for the Marvis module.

Manages pyATS connections, command execution, and output parsing.
Complies with FR6, FR7, FR8, FR9.
Uses asyncio for non-blocking operations where pyATS allows or via run_in_executor.
"""

import asyncio
import logging
import socket
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple

from genie.conf.base import Device as GenieDevice
from genie.harness.exceptions import GenieCommandError
from genie.metaparser.util.exceptions import SchemaEmptyParserError
from genie.testbed import load as load_testbed

# Assuming these are defined in data_models.py as per the project structure
from .data_models import ConnectivityTestResult, PyATSCommandResult

logger = logging.getLogger(__name__)


class PyATSHandler:
    """
    Handles interactions with network devices using pyATS and Genie.

    Complies with FR6, FR7, FR8, FR9, FR9.1.
    """

    def __init__(
        self,
        testbed_file: Optional[str] = None,
        allowed_commands: Optional[List[str]] = None,
        enable_connectivity_tests: bool = True,
    ):
        """
        Initializes the PyATSHandler.

        Args:
            testbed_file: Path to the pyATS testbed YAML file.
            allowed_commands: A list of exact show commands that are permitted to be run.
            enable_connectivity_tests: If True, basic connectivity tests (ping, DNS)
                                       will be run if a device connection fails.
        """
        self.testbed_file = testbed_file
        self.testbed: Optional[Any] = None  # pyats.topology.Testbed object
        self.allowed_commands_set: Set[str] = (
            set(" ".join(cmd.strip().split()) for cmd in allowed_commands)
            if allowed_commands
            else set()
        )
        self.enable_connectivity_tests = enable_connectivity_tests

        if self.testbed_file:
            try:
                self.testbed = load_testbed(self.testbed_file)
                logger.info(f"Successfully loaded testbed from: {self.testbed_file}")
            except Exception as e:
                logger.error(
                    f"Failed to load testbed file {self.testbed_file}: {e}",
                    exc_info=True,
                )
                self.testbed = None
        else:
            logger.warning(
                "No testbed file provided to PyATSHandler. Operations will be limited."
            )
            self.testbed = None

    def _is_command_allowed(self, command: str) -> bool:
        """Checks if the command is in the allowed list."""
        # Command should already be normalized before calling this
        return command in self.allowed_commands_set

    async def _perform_ping_async(
        self, target_ip_or_hostname: str
    ) -> ConnectivityTestResult:
        """Performs an ICMP ping to the target."""
        command = ["ping", "-c", "3", "-W", "2", target_ip_or_hostname]  # 3 packets, 2s timeout
        success = False
        details: Dict[str, Any] = {"output": "", "error": "", "latency_avg_ms": None}

        try:
            process = await asyncio.to_thread(
                subprocess.run, command, capture_output=True, text=True, timeout=10
            )
            details["output"] = process.stdout
            details["error"] = process.stderr
            if process.returncode == 0:
                success = True
                if process.stdout: # Try to parse latency for Linux ping
                    lines = process.stdout.strip().split("\\n")
                    if lines:
                        summary_line = lines[-1]
                        if "rtt" in summary_line and "avg" in summary_line:
                            try:
                                avg_latency_str = summary_line.split("/")[4]
                                details["latency_avg_ms"] = float(avg_latency_str)
                            except (IndexError, ValueError):
                                logger.debug(
                                    f"Could not parse avg latency from ping output: {summary_line}"
                                )
            else:
                logger.warning(
                    f"Ping to {target_ip_or_hostname} failed with return code {process.returncode}."
                )
        except subprocess.TimeoutExpired:
            details["error"] = "Ping command timed out."
            logger.warning(f"Ping to {target_ip_or_hostname} timed out.")
        except FileNotFoundError:
            details["error"] = "Ping command not found."
            logger.error("Ping command not found. Ensure 'ping' is in system PATH.")
        except Exception as e:
            details["error"] = f"Ping execution error: {str(e)}"
            logger.error(
                f"Error during ping to {target_ip_or_hostname}: {e}", exc_info=True
            )

        return ConnectivityTestResult(
            test_type="ping", target=target_ip_or_hostname, success=success, details=details
        )

    async def _perform_dns_resolution_async(
        self, hostname: str
    ) -> ConnectivityTestResult:
        """Performs DNS resolution for the hostname."""
        success = False
        details: Dict[str, Any] = {"resolved_ips": [], "error": None}
        try:
            _, _, ip_addresses = await asyncio.to_thread(
                socket.gethostbyname_ex, hostname
            )
            if ip_addresses:
                details["resolved_ips"] = ip_addresses
                success = True
            else:
                details["error"] = "DNS resolution returned no IP addresses."
        except socket.gaierror as e:
            details["error"] = f"DNS resolution failed: {str(e)}"
            logger.warning(f"DNS resolution for {hostname} failed: {e}")
        except Exception as e:
            details["error"] = f"DNS resolution unexpected error: {str(e)}"
            logger.error(
                f"Unexpected error during DNS resolution for {hostname}: {e}",
                exc_info=True,
            )

        return ConnectivityTestResult(
            test_type="dns_resolution", target=hostname, success=success, details=details
        )

    def get_device_object(self, device_name: str) -> Optional[GenieDevice]:
        """Retrieves a device object from the loaded testbed."""
        if not self.testbed:
            logger.warning("Cannot get device object: Testbed is not loaded.")
            return None
        device = self.testbed.devices.get(device_name)
        if not device:
            logger.warning(f"Device '{device_name}' not found in the testbed.")
        return device

    async def execute_command_on_devices(
        self, device_names: List[str], command_to_execute: str
    ) -> Tuple[List[PyATSCommandResult], List[ConnectivityTestResult]]:
        """
        Executes a single command on a list of devices.

        Args:
            device_names: List of device hostnames (must be present in the testbed).
            command_to_execute: The show command string to execute.

        Returns:
            A tuple containing:
                - A list of PyATSCommandResult objects.
                - A list of ConnectivityTestResult objects (if any were run).
        """
        all_pyats_results: List[PyATSCommandResult] = []
        all_connectivity_results: List[ConnectivityTestResult] = []

        if not self.testbed:
            logger.error("PyATSHandler cannot execute commands: Testbed is not loaded.")
            for device_name in device_names:
                all_pyats_results.append(
                    PyATSCommandResult(
                        device_hostname=device_name,
                        command=command_to_execute,
                        error="PyATSHandler misconfiguration: Testbed not loaded.",
                    )
                )
            return all_pyats_results, all_connectivity_results

        normalized_command = " ".join(command_to_execute.strip().split())

        if not self._is_command_allowed(normalized_command):
            logger.warning(
                f"Command '{normalized_command}' is not in the allowed list. "
                "Skipping execution on all devices."
            )
            for device_name in device_names:
                all_pyats_results.append(
                    PyATSCommandResult(
                        device_hostname=device_name,
                        command=normalized_command,
                        error=f"Command not allowed: '{normalized_command}'",
                    )
                )
            return all_pyats_results, all_connectivity_results

        for device_name in device_names:
            device_connectivity_tests: List[ConnectivityTestResult] = []
            device_obj = self.get_device_object(device_name)

            if not device_obj:
                all_pyats_results.append(
                    PyATSCommandResult(
                        device_hostname=device_name,
                        command=normalized_command,
                        error=f"Device '{device_name}' not found in testbed.",
                    )
                )
                continue

            connection_error_msg: Optional[str] = None
            try:
                logger.info(f"Attempting to connect to device: {device_name}...")
                if not device_obj.is_connected():
                    await asyncio.to_thread(
                        device_obj.connect, log_stdout=False, learn_hostname=True
                    )
                logger.info(f"Successfully connected to device: {device_name}")

                # If connected, proceed to execute command
                raw_output_str: Optional[str] = None
                parsed_data: Any = None
                cmd_error_str: Optional[str] = None

                try:
                    logger.debug(
                        f"Attempting to parse command '{normalized_command}' on {device_name} with raw_data=True."
                    )
                    parse_call_result = await asyncio.to_thread(
                        device_obj.parse, normalized_command, raw_data=True
                    )
                    parsed_data = parse_call_result

                    if (
                        hasattr(parse_call_result, "raw_output")
                        and isinstance(parse_call_result.raw_output, list)
                        and len(parse_call_result.raw_output) > 0
                        and isinstance(parse_call_result.raw_output[0], dict)
                        and "output" in parse_call_result.raw_output[0]
                    ):
                        raw_output_str = parse_call_result.raw_output[0]["output"]
                    else:
                        logger.debug(
                            "'raw_data=True' did not yield expected raw_output structure. "
                            "Executing for raw output separately."
                        )
                        raw_output_str = await asyncio.to_thread(
                            device_obj.execute, normalized_command
                        )

                except SchemaEmptyParserError as e_empty:
                    logger.warning(
                        f"SchemaEmptyParserError for '{normalized_command}' on {device_name}: {e_empty}. "
                        "Output was parsed as empty or did not fit schema."
                    )
                    cmd_error_str = (
                        f"Parsed output was empty or did not match schema: {str(e_empty)}"
                    )
                    parsed_data = None
                    if raw_output_str is None:
                        try:
                            raw_output_str = await asyncio.to_thread(
                                device_obj.execute, normalized_command
                            )
                        except Exception as exec_err:
                            logger.error(
                                f"Failed to execute command for raw output after SchemaEmptyParserError: {exec_err}"
                            )
                            raw_output_str = f"Failed to retrieve raw output: {exec_err}"
                except AttributeError as e_attr:
                    logger.warning(
                        f"AttributeError during parse for '{normalized_command}' on {device_name} "
                        f"(possibly missing parser or issue with device OS/state): {e_attr}"
                    )
                    cmd_error_str = (
                        f"Parsing failed (OS: {device_obj.os}, type: {device_obj.type}. "
                        f"Possibly missing parser or device state issue): {str(e_attr)}"
                    )
                    parsed_data = None
                    if raw_output_str is None:
                        try:
                            raw_output_str = await asyncio.to_thread(
                                device_obj.execute, normalized_command
                            )
                        except Exception as exec_err:
                            raw_output_str = f"Failed to retrieve raw output: {exec_err}"
                except GenieCommandError as e_cmd:
                    logger.error(
                        f"GenieCommandError for '{normalized_command}' on {device_name}: {e_cmd}",
                        exc_info=True,
                    )
                    cmd_error_str = f"Command execution or parsing error: {str(e_cmd)}"
                    parsed_data = None
                    if hasattr(e_cmd, "output") and e_cmd.output:
                        raw_output_str = str(e_cmd.output)
                    elif raw_output_str is None:
                        raw_output_str = (
                            "Failed to retrieve raw output after GenieCommandError."
                        )
                except Exception as e_gen:
                    logger.error(
                        f"Generic error during parse/execute for '{normalized_command}' on {device_name}: {e_gen}",
                        exc_info=True,
                    )
                    cmd_error_str = (
                        f"Unexpected error during command processing: {str(e_gen)}"
                    )
                    parsed_data = None
                    if raw_output_str is None:
                        raw_output_str = (
                            "Failed to retrieve raw output after generic error."
                        )
                
                if raw_output_str is not None and not isinstance(raw_output_str, str):
                    raw_output_str = str(raw_output_str)

                all_pyats_results.append(
                    PyATSCommandResult(
                        device_hostname=device_name,
                        command=normalized_command,
                        raw_output=raw_output_str,
                        parsed_output=parsed_data if not cmd_error_str else None,
                        error=cmd_error_str,
                    )
                )

            except Exception as conn_err: # Catch connection errors here
                logger.error(
                    f"Failed to connect to device {device_name}: {conn_err}",
                    exc_info=True,
                )
                connection_error_msg = f"Connection error: {str(conn_err)}"
                # Fall through to connectivity tests / error reporting

            finally:
                if device_obj.is_connected():
                    logger.info(f"Disconnecting from device: {device_name}")
                    await asyncio.to_thread(device_obj.disconnect)

            if connection_error_msg: # Handle connection failure reporting after finally block
                if self.enable_connectivity_tests:
                    target_for_ping = device_name
                    try: # Try to get IP from testbed for more reliable ping
                        conn_details = device_obj.connections.get("default") or device_obj.connections.get("a")
                        if conn_details and conn_details.ip:
                            target_for_ping = str(conn_details.ip)
                    except Exception:
                        logger.debug(f"Could not get specific IP for {device_name}, using name/IP as provided.")

                    logger.info(
                        f"Performing basic connectivity tests for {device_name} (target: {target_for_ping})."
                    )
                    ping_result = await self._perform_ping_async(target_for_ping)
                    device_connectivity_tests.append(ping_result)
                    
                    # Only run DNS if target_for_ping is likely a hostname
                    is_ip_like = all(c.isdigit() or c == '.' for c in target_for_ping.split(':')[0]) # Basic check
                    if not is_ip_like:
                        dns_result = await self._perform_dns_resolution_async(device_name) # Use original device_name for DNS
                        device_connectivity_tests.append(dns_result)
                    
                    connection_error_msg += (
                        f". Connectivity tests run. Ping success: {ping_result.success}."
                    )
                    if 'dns_result' in locals() and dns_result: # Check if dns_result was created
                         connection_error_msg += f" DNS success: {dns_result.success}."


                all_pyats_results.append(
                    PyATSCommandResult(
                        device_hostname=device_name,
                        command=normalized_command,
                        error=connection_error_msg,
                    )
                )
            
            all_connectivity_results.extend(device_connectivity_tests)

        return all_pyats_results, all_connectivity_results