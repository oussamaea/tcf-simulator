
import time, json
from .openai_client import get_client, get_models
from .logger import log, log_exception

def chat_json(system: str, user: str, *, response_format="json_object", max_retries=5):
    client = get_client()
    gen_model, *_ = get_models()
    delays = [0, 4, 8, 12, 16]
    last_err = None
    for d in delays[:max_retries]:
        if d:
            time.sleep(d)
        try:
            resp = client.chat.completions.create(
                model=gen_model,
                response_format={"type": response_format},
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            log_exception("chat_json error", e)
            if "rate limit" in msg or "429" in msg or "timeout" in msg:
                continue
            else:
                break
    raise last_err
