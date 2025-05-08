"""
Handles pyATS device connections and command execution for the Marvis module.

Manages pyATS connections, command execution, and output parsing.
Complies with FR6, FR7, FR8, FR9.
Uses asyncio for non-blocking operations where pyATS allows or via run_in_executor.
"""