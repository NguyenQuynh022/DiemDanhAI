from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import requests

from services.chatbot_prompt import (
    build_student_prompt,
    build_lecturer_prompt
)

chatbot_bp = Blueprint("chatbot", __name__)

# =========================================================
# CONFIG
# =========================================================

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


# =========================================================
# ANTHROPIC
# =========================================================

def _call_anthropic(system_prompt: str, user_message: str) -> str:
    api_key = current_app.config.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return "⚠️ Chưa cấu hình ANTHROPIC_API_KEY."

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": user_message
            }
        ],
    }

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        resp.raise_for_status()

        data = resp.json()

        if (
            "content" in data
            and isinstance(data["content"], list)
            and len(data["content"]) > 0
        ):
            return data["content"][0]["text"].strip()

        return "❌ Không nhận được phản hồi từ Claude."

    except requests.exceptions.Timeout:
        return "⏱️ Claude timeout."

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "?"

        if status == 401:
            return "❌ API key Claude không hợp lệ."

        if status == 429:
            return "⚠️ Claude đang quá tải."

        return f"❌ Claude API Error ({status})"

    except Exception as e:
        return f"❌ Lỗi Claude: {str(e)}"


# =========================================================
# GROQ
# =========================================================

def _call_groq(system_prompt: str, user_message: str) -> str:
    api_key = current_app.config.get("GROQ_API_KEY", "")

    if not api_key:
        return "⚠️ Chưa cấu hình GROQ_API_KEY."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.7
    }

    try:
        resp = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        resp.raise_for_status()

        data = resp.json()

        if (
            "choices" in data
            and len(data["choices"]) > 0
        ):
            return data["choices"][0]["message"]["content"].strip()

        return "❌ Không nhận được phản hồi từ Groq."

    except requests.exceptions.Timeout:
        return "⏱️ Groq timeout."

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "?"

        try:
            print("GROQ ERROR:", e.response.json())
        except:
            print("GROQ ERROR:", str(e))

        if status == 401:
            return "❌ API key Groq không hợp lệ."

        if status == 429:
            return "⚠️ Groq đang quá tải."

        return f"❌ Groq API Error ({status})"

    except Exception as e:
        return f"❌ Lỗi Groq: {str(e)}"


# =========================================================
# GEMINI
# =========================================================

def _call_gemini(system_prompt: str, user_message: str) -> str:
    return "❌ Gemini chưa được cấu hình."


# =========================================================
# MAIN ROUTER
# =========================================================

def _call_chatbot(system_prompt: str, user_message: str) -> str:
    provider = current_app.config.get(
        "AI_PROVIDER",
        "groq"
    ).lower()

    if provider == "groq":
        return _call_groq(system_prompt, user_message)

    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_message)

    if provider == "gemini":
        return _call_gemini(system_prompt, user_message)

    return f"❌ AI provider không hợp lệ: {provider}"


def _build_message_from_payload(data: dict) -> str:
    message = data.get("message")

    if isinstance(message, str) and message.strip():
        return message.strip()

    messages = data.get("messages")

    if isinstance(messages, list) and len(messages) > 0:
        last = messages[-1]

        if isinstance(last, dict):
            return str(last.get("content", "")).strip()

    return ""


def _make_response(reply: str):
    if (
        isinstance(reply, str)
        and (
            reply.startswith("❌")
            or reply.startswith("⚠️")
        )
    ):
        return jsonify({
            "ok": False,
            "error": reply
        })

    return jsonify({
        "ok": True,
        "reply": reply
    })


# =========================================================
# STATUS
# =========================================================

@chatbot_bp.route("/chatbot/api/status", methods=["GET"])
def chatbot_status():

    provider = current_app.config.get(
        "AI_PROVIDER",
        "groq"
    ).lower()

    if provider == "groq":
        provider_key = current_app.config.get(
            "GROQ_API_KEY",
            ""
        )

    elif provider == "anthropic":
        provider_key = current_app.config.get(
            "ANTHROPIC_API_KEY",
            ""
        )

    elif provider == "gemini":
        provider_key = current_app.config.get(
            "GEMINI_API_KEY",
            ""
        )

    else:
        provider_key = ""

    return jsonify({
        "ready": bool(provider_key),
        "provider": provider,
    })


# =========================================================
# CHAT
# =========================================================

@chatbot_bp.route("/chatbot/api/chat", methods=["POST"])
@login_required
def chat():

    data = request.get_json(silent=True) or {}

    message = _build_message_from_payload(data)

    if not message:
        return jsonify({
            "ok": False,
            "error": "Tin nhắn trống"
        }), 400

    # STUDENT
    if current_user.role == "student":
        system_prompt = build_student_prompt(current_user)

    # LECTURER
    elif current_user.role == "lecturer":
        system_prompt = build_lecturer_prompt(current_user)

    # DEFAULT
    else:
        system_prompt = (
            "Bạn là trợ lý AI của EduPortal. "
            "Trả lời ngắn gọn bằng tiếng Việt."
        )

    reply = _call_chatbot(system_prompt, message)

    return _make_response(reply)