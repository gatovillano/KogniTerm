import pytest
from langchain_core.messages import HumanMessage
from kogniterm.core.agents.super_agent import _langchain_to_dict_messages
from kogniterm.core.antigravity_client import AntigravityClient
from kogniterm.core.history_manager import HistoryManager
from kogniterm.core.llm_service import LLMService

def test_super_agent_preserves_multimodal_list():
    img_block = {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}
    }
    text_block = {"type": "text", "text": "Describe this image"}
    human_msg = HumanMessage(content=[text_block, img_block])

    dict_msgs = _langchain_to_dict_messages([human_msg])
    assert len(dict_msgs) == 1
    assert dict_msgs[0]["role"] == "user"
    assert isinstance(dict_msgs[0]["content"], list)
    assert len(dict_msgs[0]["content"]) == 2
    assert dict_msgs[0]["content"][0] == text_block
    assert dict_msgs[0]["content"][1] == img_block

def test_antigravity_client_maps_data_url_image():
    client = AntigravityClient()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze image"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    }
                }
            ]
        }
    ]

    contents, system_instruction = client.map_messages(messages)
    assert len(contents) == 1
    content = contents[0]
    assert content["role"] == "user"
    assert len(content["parts"]) == 2
    assert content["parts"][0]["text"] == "Analyze image"
    assert content["parts"][1]["inlineData"]["mimeType"] == "image/png"
    assert "data" in content["parts"][1]["inlineData"]

def test_token_counting_does_not_inflate_images(tmp_path):
    large_b64 = "A" * 100000
    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "test prompt"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{large_b64}"}}
        ]
    }

    # HistoryManager sanitization
    hm = HistoryManager(history_file_path=str(tmp_path / "hist.json"))
    sanitized = hm._to_litellm_message_for_len_calc(msg)
    assert "IMAGE_PLACEHOLDER" in sanitized["content"][1]["image_url"]["url"]

    # LLMService token count
    service = LLMService(use_multi_provider=False)
    token_count = service._get_messages_token_count([msg])
    # Must be reasonably small (< 2000 tokens), not 25,000+ tokens
    assert token_count < 2000
