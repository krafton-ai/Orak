from typing import Dict, List, Any
import json
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from mcp_agent_servers.setup_openai import setup_openai

setup_openai()

class SkillManager:
    def __init__(self, path):
        self.save_path = f"data/skills/{path.replace('logs/', '', 1)}/"
        self.skills: Dict[str, List[Any]] = {}
        self.vectordb = Chroma(
            collection_name="skill_vectordb",
            embedding_function=OpenAIEmbeddings(),
            persist_directory=self.save_path,
        )
        self.retrieval_top_k = 5
    
    def add_new_skill(self, skill_name: str, skill: str, description: str) -> None:
        if all((skill_name, skill, description)): # if all not None
            self.skills[skill_name] = {
                "skill": skill,
                "description": description,
            }
            self.vectordb.add_texts(
                texts=[description],
                ids=[skill_name],
                metadatas=[{"name": skill_name}],
            )
            assert self.vectordb._collection.count() == len(
                self.skills
            ), "vectordb is not synced with skills dictionary"
    
    def retrieve_skills(self, query: str) -> str:
        k = min(self.vectordb._collection.count(), self.retrieval_top_k)
        if k == 0 or query is None:
            return ""
        docs_and_scores = self.vectordb.similarity_search_with_score(query, k=k)
        
        retrieved_skill_names = [doc.metadata['name'] for doc, _ in docs_and_scores]
        retrieved_skills = '\n\n'.join([self.skills[name]["skill"] for name in retrieved_skill_names])

        # save retrieved_skills.txt
        with open(f'{self.save_path}retrieved_skills.txt', 'w+') as file:
            file.write(retrieved_skills)

        return retrieved_skills