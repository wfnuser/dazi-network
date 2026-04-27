import json
import httpx
from app.config import settings

_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def _chat_completion(system_prompt: str, user_prompt: str) -> str:
    """Call MiniMax chat completion API."""
    client = await get_http_client()
    resp = await client.post(
        f"{settings.minimax_base_url}/text/chatcompletion_v2",
        headers={
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.minimax_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


AI_EXTRACT_SYSTEM_PROMPT = """\
你是一个社交匹配系统的后端分析引擎。用户提供了3段自我描述标签。
请从中提取5个维度的信息，以JSON格式返回：

{
  "summary": "一句话总结这个人（30字以内）",
  "personality": "性格特征（如MBTI倾向、社交风格、做事方式）",
  "interests": "兴趣爱好（具体的活动、领域）",
  "values": "价值观和生活态度（什么对TA重要）",
  "lifestyle": "生活方式（作息、消费、城市、习惯）"
}

只返回JSON，不要其他内容。每个字段30-80字中文。"""


async def generate_ai_extracted(tags: list[str]) -> dict[str, str]:
    """Generate ai_extracted from user tags using LLM."""
    user_prompt = f"用户的3个自我描述标签：\n1. {tags[0]}\n2. {tags[1]}\n3. {tags[2]}"
    raw = await _chat_completion(AI_EXTRACT_SYSTEM_PROMPT, user_prompt)

    # Parse JSON from response (strip markdown code fences if present)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    result = json.loads(cleaned)

    required = {"summary", "personality", "interests", "values", "lifestyle"}
    if not required.issubset(result.keys()):
        raise ValueError(f"LLM response missing fields: {required - result.keys()}")
    return {k: str(v) for k, v in result.items() if k in required}


INTENT_PARSE_SYSTEM_PROMPT = """\
你是一个社交匹配系统的查询解析引擎。用户用自然语言描述了他想找什么样的搭子。
请解析用户意图，返回JSON：

{
  "filters": {
    "city": "城市名（如有）或null",
    "age_min": 数字或null,
    "age_max": 数字或null,
    "gender": "M/F/O（如有）或null"
  },
  "dimensions": ["要使用的embedding维度列表"],
  "query_embedding_text": "用于生成query embedding的文本（概括用户在找什么样的人）"
}

dimensions 可选值: summary, personality, interests, values, lifestyle
规则:
- 不是所有维度都用，选择性激活1-3个最相关的维度
- "找聊得来的" → ["personality"]
- "找旅行搭子" → ["interests", "lifestyle"]
- "价值观相近" → ["values"]
- "找独立开发搭子" → ["interests"]
- "随便找找" → ["summary"]
- 含性格描述 → 加 "personality"
- 含具体爱好 → 加 "interests"

filters中为null的字段表示不筛选。只返回JSON。"""


async def parse_search_intent(intent: str) -> dict:
    """Parse raw search intent into filters + dimensions using LLM."""
    raw = await _chat_completion(INTENT_PARSE_SYSTEM_PROMPT, f"用户说: {intent}")

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    result = json.loads(cleaned)

    # Sanitize filters — remove null values
    filters = result.get("filters", {})
    filters = {k: v for k, v in filters.items() if v is not None}

    dimensions = result.get("dimensions", ["summary"])
    if not dimensions:
        dimensions = ["summary"]
    # Validate dimensions
    valid_dims = {"summary", "personality", "interests", "values", "lifestyle"}
    dimensions = [d for d in dimensions if d in valid_dims]
    if not dimensions:
        dimensions = ["summary"]

    query_text = result.get("query_embedding_text", intent)

    return {
        "filters": filters,
        "dimensions": dimensions,
        "query_embedding_text": query_text,
    }
