from pydantic import BaseModel

SCHEMA_REGISTRY = {}

def register_schema(cls):
    SCHEMA_REGISTRY[cls.__name__] = cls.model_json_schema()
    return cls

@register_schema
class ActionSchema(BaseModel):
    reasoning: str
    action: str

@register_schema
class ReflectionSchema(BaseModel):
    self_reflection: str
    self_reflection_summary: str
