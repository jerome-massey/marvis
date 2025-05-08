"""
LLM Interaction Handler for the Marvis module using Pydantic AI.

Manages all interactions with the Large Language Model (LLM)
using Pydantic AI for structured input and output.
Complies with FR1, FR2, FR3, FR5 (generation of structured request), FR11.
"""
import logging
from typing import Type, TypeVar, Optional, List, Dict, Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import PydanticAIException, ModelError
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart # SystemMessage could be used if needed

T_OutputModel = TypeVar("T_OutputModel", bound=BaseModel)

logger = logging.getLogger(__name__)

class LLMHandler:
    """
    Manages interactions with the Large Language Model (LLM)
    using Pydantic AI for structured input and output.
    """

    def __init__(self, llm_config: Dict[str, Any]):
        """
        Initializes the LLMHandler with configuration for Pydantic AI.

        Args:
            llm_config (Dict[str, Any]): Configuration dictionary. Expected keys:
                - "provider": (str) e.g., "google-gla", "openai"
                - "model_name": (str) e.g., "gemini-1.5-flash", "gpt-4o"
                - "api_key": (Optional[str]) API key if not set via environment variables.
                             Pydantic AI typically prefers env vars (e.g., GEMINI_API_KEY, OPENAI_API_KEY).
                - "temperature": (Optional[float]) LLM temperature.
                - "max_tokens": (Optional[int]) Max tokens for LLM response.
                - "system_prompt_template": (Optional[str]) Base system prompt/instructions.
                - "pyats_capabilities_prompt_section": (Optional[str]) Template for informing LLM about pyATS capabilities.
        """
        self.llm_config = llm_config
        self.provider = str(llm_config.get("provider"))
        self.model_name = str(llm_config.get("model_name"))
        
        if not self.provider or not self.model_name:
            raise ValueError("LLM provider and model_name must be specified in llm_config.")

        self.pydantic_ai_model_str = f"{self.provider}:{self.model_name}"
        
        self.model_settings: Dict[str, Any] = {}
        if "temperature" in llm_config:
            self.model_settings["temperature"] = float(llm_config["temperature"])
        if "max_tokens" in llm_config:
            self.model_settings["max_tokens"] = int(llm_config["max_tokens"])
        # Add other Pydantic AI ModelSettings as needed from llm_config

        self.system_prompt_template = str(llm_config.get(
            "system_prompt_template", 
            "You are an advanced AI assistant specializing in network troubleshooting. "
            "Analyze the provided information and respond in the requested structured format."
        ))
        self.pyats_capabilities_prompt_section = str(llm_config.get(
            "pyats_capabilities_prompt_section",
            "To gather information from network devices, you can request specific pyATS/Genie operations. "
            "Structure your request for data using the fields provided in the output model. "
            "Available capabilities include:"
        ))
        # Note: API key handling is mostly done by Pydantic AI via environment variables
        # (e.g., GEMINI_API_KEY for google-gla, OPENAI_API_KEY for openai)
        # or by directly instantiating providers if needed. This implementation relies on
        # Pydantic AI's default mechanisms for resolving credentials.

    def _construct_instructions(
        self, 
        custom_instructions: Optional[str] = None,
        pyats_capabilities_summary: Optional[str] = None
    ) -> str:
        """
        Constructs the full system instructions for the LLM.
        FR2: Dynamic Prompt Formulation.
        """
        base_instructions = custom_instructions if custom_instructions else self.system_prompt_template
        
        if pyats_capabilities_summary:
            # Ensure there's a clear separation and introduction for capabilities
            if self.pyats_capabilities_prompt_section.endswith(":"):
                cap_prompt = f"\n\n{self.pyats_capabilities_prompt_section}\n{pyats_capabilities_summary}"
            else:
                cap_prompt = f"\n\n{self.pyats_capabilities_prompt_section}: {pyats_capabilities_summary}"
            base_instructions += cap_prompt
            
        return base_instructions

    async def get_structured_response(
        self,
        user_query: str,
        output_model: Type[T_OutputModel],
        current_context: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        pyats_capabilities_summary: Optional[str] = None,
        custom_instructions_override: Optional[str] = None,
    ) -> T_OutputModel:
        """
        Interacts with the LLM to get a structured response.

        FR1: LLM Configuration (handled in init and here by creating Agent)
        FR2: Dynamic Prompt Formulation (handled by _construct_instructions and inputs)
        FR3: LLM Response Processing (Pydantic AI Agent handles parsing to output_model)
        FR11: Data Preparation for LLM (current_context, chat_history)

        Args:
            user_query (str): The primary user query or task for the LLM.
            output_model (Type[T_OutputModel]): The Pydantic model to structure the LLM's response.
            current_context (Optional[str]): Additional context for the current query (e.g., alarm details, device data).
            chat_history (Optional[List[Dict[str, str]]]): Conversation history.
                Each dict should have "role" ("user" or "assistant") and "content".
            pyats_capabilities_summary (Optional[str]): A summary of available pyATS commands/capabilities
                                                        to guide the LLM.
            custom_instructions_override (Optional[str]): Specific instructions for this call, overriding
                                                          the default system_prompt_template.

        Returns:
            T_OutputModel: An instance of the provided output_model, populated by the LLM.

        Raises:
            PydanticAIException: If Pydantic AI encounters an issue.
            ValueError: If input parameters are invalid.
            ModelError: If the LLM fails to produce a valid response after retries.
        """
        logger.debug(
            f"Requesting structured response. Output model: {output_model.__name__}, User query: '{user_query[:100]}...'"
        )

        instructions = self._construct_instructions(
            custom_instructions=custom_instructions_override,
            pyats_capabilities_summary=pyats_capabilities_summary
        )

        agent_message_history: List[Any] = [] # Using Any for Pydantic AI message types
        if chat_history:
            for entry in chat_history:
                role = str(entry.get("role", "")).lower()
                content = str(entry.get("content", ""))
                if not content: 
                    logger.debug(f"Skipping empty message in chat history for role '{role}'.")
                    continue

                if role == "user":
                    agent_message_history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
                elif role == "assistant":
                    # ModelResponse requires a model_name. Using a placeholder for reconstructed history.
                    agent_message_history.append(ModelResponse(parts=[TextPart(content=content)], model_name="history_assistant_reply"))
                else:
                    logger.warning(f"Unsupported role '{role}' in chat history, skipping message: '{content[:50]}...'.")
        
        prompt_content = user_query
        if current_context:
            prompt_content = f"Context:\n{current_context}\n\nTask:\n{user_query}"

        try:
            agent = Agent(
                model=self.pydantic_ai_model_str,
                output_type=output_model,
                instructions=instructions,
                model_settings=self.model_settings if self.model_settings else None,
            )
            
            logger.debug(f"Agent created for model {self.pydantic_ai_model_str} with output type {output_model.__name__}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Instructions for LLM (first 200 chars): {instructions[:200]}")
                logger.debug(f"Prompt content for LLM (first 200 chars): {prompt_content[:200]}")
                if agent_message_history:
                    logger.debug(f"Message history being sent (count): {len(agent_message_history)}")
                    for i, msg in enumerate(agent_message_history[:2]): # Log first 2 messages
                         logger.debug(f"History msg [{i}]: Role: {type(msg).__name__}, Content: {str(msg.content)[:100]}...")


            run_result = await agent.run(
                prompt_content,
                message_history=agent_message_history if agent_message_history else None
            )
            
            logger.debug(f"LLM run completed. Raw output type from Pydantic AI: {type(run_result.output)}")

            if not isinstance(run_result.output, output_model):
                error_msg = (
                    f"LLM output was not of the expected type {output_model.__name__}. "
                    f"Got: {type(run_result.output)}. Value: {run_result.output!r}"
                )
                logger.error(error_msg)
                raise PydanticAIException(error_msg)

            logger.info(f"Successfully received and parsed structured response of type {output_model.__name__}.")
            return run_result.output

        except ModelError as e:
            logger.error(f"LLM ModelError for {self.pydantic_ai_model_str}: {e}. Review LLM logs and prompt if issues persist.", exc_info=True)
            raise
        except PydanticAIException as e:
            logger.error(f"Pydantic AI Exception during LLM interaction with {self.pydantic_ai_model_str}: {e}", exc_info=True)
            raise 
        except Exception as e:
            logger.error(f"An unexpected error occurred in LLMHandler with {self.pydantic_ai_model_str}: {e}", exc_info=True)
            raise PydanticAIException(f"Unexpected error in LLMHandler with {self.pydantic_ai_model_str}: {e}") from e