from abc import ABC, abstractmethod
from typing import Union, Sequence
import base64
import enum
import os
import logging
import io
import numpy as np
import json
import asyncio

from typing import Any, Literal
from concurrent.futures import ThreadPoolExecutor

from google.genai import Client as GeminiClient
from google.genai.local_tokenizer import LocalTokenizer
from google.genai.types import (
    HttpOptions as GeminiHttpOptions,
    Part as GeminiPart,
    GenerateContentConfig,
    Content as GeminiContent,
    Blob as GeminiBlob,
    FinishReason as GeminiFinishReason,
    ThinkingConfig as GeminiThinkingConfig,
    AutomaticFunctionCallingConfig,
)
from google.oauth2 import service_account
from json_repair import repair_json
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field


_LOGGER = logging.getLogger(__name__)


class CompareSchema(BaseModel):
    answer: bool


class DocQAResponse(BaseModel):
    answer: str
    sources: list[str]

# class DocQAResponse(BaseModel):
#     full_answer: str = Field(..., description="Full textual answer returned by the model.")
#     sources: list[str] = Field(..., description="List of source identifiers or citations referenced by the answer.")
#     number: float | int | None = Field(
#         None, description="Extracted numeric answer if applicable (can be int or float)."
#     )
#     text: str | None = Field(None, description="Extracted short text answer or snippet.")
#     date: str | None = Field(None, description="Extracted date string if applicable.")
#     yes_no: str | None = Field(None, description="Yes/No response when applicable.")


class LogoSchema(BaseModel):
    markdown: str = Field(default="Captioning not available.")
    category: Literal["logo", "not_logo"] = "not_logo"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ImageContent(BaseModel):
    format: Literal["jpeg", "png", "gif"] = "jpeg"
    base64_data: str | None


class LLMMessage(BaseModel):
    role: MessageRole
    content: list[str | ImageContent]
    model_config = ConfigDict(arbitrary_types_allowed=True)


class CompletionTokenLogprob(BaseModel):
    token: str
    logprob: float


class TokensUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    incomplete: bool
    response: str
    logprobs: list[CompletionTokenLogprob] | None = None
    tokens_usage: TokensUsage | None = None


def is_repeating_pattern(
    tokens: list[str], max_sequence_length: int = 256, min_repetitions: int = 10
) -> bool:
    """
    Checks if the given string has the same string with up to
    max_sequence_length repeating at least min_repetitions times
    in the end of the string.
    """
    for i in range(1, max_sequence_length + 1):
        if len(tokens) < i * min_repetitions:
            continue
        pattern = tokens[-i:]
        if pattern * min_repetitions == tokens[-i * min_repetitions :]:
            return True
    return False


def array_to_b64(img: np.ndarray, format: str = "JPEG") -> str:
    img_pil = Image.fromarray(img)
    if img_pil.mode == "RGBA":
        img_pil = img_pil.convert("RGB")
    buffered = io.BytesIO()
    img_pil.save(buffered, format=format)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_b64


class AsyncGeminiStreamingClient():
    def __init__(self, secrets: dict[str, str], model_name: str) -> None:

        self.model_name = model_name
        self.model = model_name
        self.secrets = secrets

        _LOGGER.info(f"Using Gemini service with model {self.model}")

    async def _convert_messages_to_api_format(
        self,
        messages: list[LLMMessage],
    ) -> tuple[str | None, list[GeminiContent]]:
        """Convert LLMMessage list to OpenAI message format"""

        system_instruction = None
        gemini_contents = []

        for imessage, message in enumerate(messages):
            if message.role == MessageRole.SYSTEM:
                assert (
                    imessage == 0
                ), "If system prompt is specified, it should come at the beginning."
                assert (
                    len(message.content) == 1 and isinstance(message.content[0], str)
                ), "Only a single text prompt is allowed for system prompt."
                item = message.content[0]
                system_instruction = item

            parts = []

            for item in message.content:
                if isinstance(item, str):
                    parts.append(GeminiPart(text=item))
                elif isinstance(item, ImageContent):
                    # Add image content
                    if item.base64_data:
                        parts.append(
                            GeminiPart(
                                inline_data=GeminiBlob(
                                    data=base64.b64decode(item.base64_data),
                                    mime_type=f"image/{item.format}",
                                )
                            )
                        )
                else:
                    raise NotImplementedError(f"Unsupported content type: {type(item)}")

            if message.role == MessageRole.USER:
                gemini_role = "user"
            elif message.role == MessageRole.ASSISTANT:
                gemini_role = "model"
            elif message.role == MessageRole.SYSTEM:
                gemini_role = "system"
            else:
                raise NotImplementedError(f"Unsupported message role: {message.role}")

            gemini_contents.append(
                GeminiContent(
                    parts=parts,
                    role=gemini_role,
                )
            )

        return system_instruction, gemini_contents

    def _get_client(self) -> GeminiClient:
        if len(self.secrets):
            creds = service_account.Credentials.from_service_account_info(
                self.secrets,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            creds = None
        return GeminiClient(
            vertexai=True,
            project="ade-vertex",
            location="global",
            credentials=creds,
        )

    def _get_generate_content_config(
        self,
        system_instruction: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        top_k: int = None,
        top_p: float = 0.0,
        logprobs: bool = False,
        response_schema: list[dict[str, Any]] | dict[str, Any] | None = None,
        timeout: float | None = None,
        thinking_budget: int | None = None,
    ) -> GenerateContentConfig:
        return GenerateContentConfig(
            response_modalities=["TEXT"],
            system_instruction=system_instruction,
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            logprobs=1 if logprobs else None,
            response_logprobs=True if logprobs else None,
            response_mime_type=(
                "application/json" if response_schema is not None else None
            ),
            response_schema=response_schema,
            thinking_config=(
                GeminiThinkingConfig(
                    thinking_budget=thinking_budget,
                )
                if thinking_budget is not None
                else None
            ),
            http_options=GeminiHttpOptions(
                timeout=(
                    timeout * 1000 if timeout is not None else None
                ),  # Timeout in milliseconds
            ),
            automatic_function_calling=AutomaticFunctionCallingConfig(
                disable=True
            ),  # Otherwise it will say "AFC is enabled..."

        )

    async def generate_response(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        top_k: int = None,
        top_p: float = 0.0,
        logprobs: bool = False,
        response_schema: list[dict[str, Any]] | dict[str, Any] | None = None,
        timeout: float | None = None,
        thinking_budget: int | None = None,
    ) -> LLMResponse:
        if logprobs:
            raise NotImplementedError(
                "returning logprobs is not yet supported for streaming mode in newer Gemini models: https://github.com/google-gemini/deprecated-generative-ai-python/issues/238#issuecomment-3048306251"
            )
        client = self._get_client()

        system_instruction, contents = await self._convert_messages_to_api_format(
            messages
        )

        response = await client.aio.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=self._get_generate_content_config(
                system_instruction=system_instruction,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                logprobs=logprobs,
                response_schema=response_schema,
                timeout=timeout,
                thinking_budget=thinking_budget,
            ),
        )

        response_text = ""
        incomplete_response = False
        tokens = []
        last_checked_num_tokens = 0
        input_tokens = None
        output_tokens = None
        local_tokenizer = LocalTokenizer(self.model_name)

        async for chunk in response:
            if (finish_reason := chunk.candidates[0].finish_reason) is not None:
                if finish_reason != GeminiFinishReason.STOP:
                    incomplete_response = True
            if chunk.usage_metadata.prompt_token_count is not None:
                input_tokens = chunk.usage_metadata.prompt_token_count
            if chunk.usage_metadata.candidates_token_count is not None:
                # Output tokens is thoughts + candidates (https://ai.google.dev/gemini-api/docs/thinking#pricing)
                num_thinking_tokens = chunk.usage_metadata.thoughts_token_count or 0
                output_tokens = (
                    num_thinking_tokens + chunk.usage_metadata.candidates_token_count
                )

            if chunk.candidates[0].content.parts is None:
                continue
            delta = chunk.candidates[0].content.parts[0].text
            chunk_tokens = (
                local_tokenizer.compute_tokens(contents=delta).tokens_info[0].token_ids
            )
            tokens.extend(chunk_tokens)
            response_text += delta

            # Since the API returns in batches, just check frequently enough
            if (len(tokens) - last_checked_num_tokens) > 20:
                if is_repeating_pattern(tokens):
                    _LOGGER.warning(
                        f"Detected repeating pattern in response, stopping the stream: {response_text}"
                    )
                    incomplete_response = True
                    break
                last_checked_num_tokens = len(tokens)

        if input_tokens is None or output_tokens is None:
            _LOGGER.warning(
                "Token usage information not available in the response, "
                "estimating input tokens."
            )
            # This IS another API call, but hopefully it does not happen too frequently.
            # We cannot use the LocalTokenizer because it only supports text types.
            input_tokens = client.models.count_tokens(
                model=self.model,
                contents=contents,
            ).total_tokens
            output_tokens = len(tokens)

        # Workaround to suppress warning: https://github.com/googleapis/python-genai/issues/1388
        if client._api_client._aiohttp_session is not None:
            await client._api_client._aiohttp_session.close()

        return LLMResponse(
            incomplete=incomplete_response,
            response=(
                # Try to repair incomplete JSON if schema is provided
                repair_json(response_text)
                if response_schema
                else response_text
            ),
            logprobs=None,  # Not supported
            tokens_usage=TokensUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )


async def main(context: str = "", question: [Sequence[str]] = [""], schema: Any = None):
    creds_json = os.getenv("GEMINI_CREDENTIALS_JSON")
    if creds_json is None:
        secrets = {}
    else:
        secrets = json.loads(creds_json)

    # client = AsyncGeminiStreamingClient(secrets, model_name="gemini-2.5-flash")
    client = AsyncGeminiStreamingClient(secrets, model_name="gemini-2.5-flash-lite")
    # image_path = "path_to_img"
    # image_path = "/mnt/data/runs/docs/cls/reg_set_full/caption_error_repeat/crops/I-216014_Redacted 2/chunk_5.png"
    # img = np.array(Image.open(image_path).convert("RGB"))
    # img_b64 = array_to_b64(img, format="png")
    # prompt = """
    #     Analyze this document element, which appears to be a logo or brand identifier.

    #     ## **Instructions**
    #     - Identify the **company, organization, or brand** represented.

    #     ✅ **Output Requirements**
    #     - Return in a json format as shown in the following pydantic. No commentary, only valid JSON.
    #     ```python
    #     from typing import Dict
    #     from pydantic import BaseModel

    #     # Logo schema
    #     class OutputSchema(BaseModel):
    #         summary: str = Field(default=DEFAULT_MARKDOWN)
    #         category: Literal["header", "text"] = "text"
    #         markdown: str = Field(default=DEFAULT_MARKDOWN)

    #     ```

    #     Where category is `logo` only if the content is about any kind of logo.
    # """

    messages = [
        LLMMessage(
            role=MessageRole.USER,
            content=[
                context,
                # ImageContent(format="png", base64_data=img_b64)
            ],
        ),
        LLMMessage(
            role=MessageRole.USER,
            content=question,
        ),
    ]
    response_schema = schema.model_json_schema()

    response = await client.generate_response(
        messages,
        response_schema=response_schema,
    )

    # print("Response:", response.response)
    # print("Incomplete:", response.incomplete)
    print("Tokens usage:", response.tokens_usage)

    return response.response


async def main_batched(
    batched_input: list[dict],
    schema: Any = None,
    concurrency: int = 10,
):
    creds_json = os.getenv("GEMINI_CREDENTIALS_JSON")
    if creds_json is None:
        secrets = {}
    else:
        secrets = json.loads(creds_json)

    client = AsyncGeminiStreamingClient(secrets, model_name="gemini-2.5-flash")

    responses = []

    sem = asyncio.Semaphore(concurrency)

    async def _generate_one(ctx: str, q: Sequence[str]) -> str | None:
        messages = [
            LLMMessage(role=MessageRole.USER, content=[ctx]),
            LLMMessage(role=MessageRole.USER, content=q),
        ]
        try:
            async with sem:
                resp = await client.generate_response(
                    messages,
                    response_schema=schema.model_json_schema() if schema else None,
                )
            return resp.response
        except Exception as exc:
            _LOGGER.exception("Error generating response for context: %s", exc)
            return None

    async def _generate_and_assign(item: dict) -> dict:
        # extract context & question(s)
        if isinstance(item, dict):
            ctx = item.get("context") or item.get("ctx") or ""
            q = item.get("question") or item.get("questions") or item.get("q") or []
        else:
            try:
                ctx, q = item[0], item[1]
            except Exception:
                ctx, q = "", []

        try:
            pred = await _generate_one(ctx, [q])
            pred = json.loads(pred) if pred else {}
            item["pred"] = pred.get("answer", "")
            item["sources"] = pred.get("sources", [])
        except Exception as exc:
            _LOGGER.exception("Failed to generate/assign pred: %s", exc)
            item["pred"] = ""
            item["sources"] = []
            item["pred_error"] = str(exc)
        return item

    # create tasks for all items (bounded concurrency enforced by semaphore inside _generate_one)
    tasks = [asyncio.create_task(_generate_and_assign(item)) for item in batched_input]
    await asyncio.gather(*tasks)

    return batched_input


# if __name__ == "__main__":
#     import asyncio
#     import json

#     logging.basicConfig(level=logging.INFO)

#     asyncio.run(main())
