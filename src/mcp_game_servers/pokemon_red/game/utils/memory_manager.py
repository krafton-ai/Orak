import json
import re

def extract_memory_entries(reflection: str) -> list[str]:
    """
    Extracts the memory_entries_to_add list from the LLM's ### Self_reflection block.
    """
    # Step 1: Remove markdown code block markers (```json ... ```)
    json_str = re.sub(r"^```json\s*|\s*```$", "", reflection.strip(), flags=re.DOTALL)
    json_str = re.sub(r"^'''json\s*|\s*'''$", "", json_str.strip(), flags=re.DOTALL)
    
    try:
        reflection_json = json.loads(json_str)
        return reflection_json.get("NewFacts", [])
    except:
        return None

def build_memory_query(goal_description: str, current_state_text: str) -> str:
    """
    Generates a memory retrieval query by combining the current goal and relevant context.
    """
    return f"Information related to 'Goal: {goal_description}' based on 'Context: {current_state_text}'"