# flake8: noqa

AGENT_MODULES = {
    "zeroshot_agent": [
        "action_inference"
    ],
    "reflection_agent": [
        "self_reflection",
        "action_inference"
    ],
    "planning_agent": [
        "subtask_planning",
        "action_inference"
    ],
    "reflection_planning_agent": [
        "self_reflection",
        "subtask_planning",
        "action_inference"
    ],
    "stardew_velly_agent": [
        "self_reflection",
        "subtask_planning",
        "action_inference"
    ],
    "skill_management_agent": [
        "self_reflection",
        "knowledge_retrieval",
        "subtask_planning",
        "skill_management",
        "action_inference"
    ],
    "street_fighter_agent": [
        "action_inference"
    ],
    "pwaat_agent": [
        "self_reflection",
        "long_term_management",
        "action_inference"
    ],
    "pokemon_agent": [
        "history_summarization",
        "memory_management",
        "self_reflection",
        "memory_management",
        "subtask_planning",
        "memory_management",
        "action_inference",
        "action_execution"
    ]
}

# More AGENT TYPES?
# ReACT ...
# ["self_reflection", "subtask_planning", "knowledge_retrieval", "action_inference"]