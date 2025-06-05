import os
from typing import Dict

base_dir = os.path.dirname(os.path.abspath(__file__))
OPENAI_KEY_PATH = os.path.join(base_dir, "keys/openai-key/key.env")

def setup_openai(
    key_path: os.PathLike = OPENAI_KEY_PATH,
) -> Dict[str, str]:
    with open(key_path, "r") as f:
        key_list = f.readlines()

    if len(key_list) > 1:
        api_key = key_list[0].strip()
        organization_key = key_list[1].strip()
        os.environ["OPENAI_ORGANIZATION"] = organization_key
        os.environ["OPENAI_API_KEY"] = api_key
        return {"organization": organization_key, "api_key": api_key}
    else:
        api_key = key_list[0].strip()
        os.environ["OPENAI_API_KEY"] = api_key
        return {"api_key": api_key}
