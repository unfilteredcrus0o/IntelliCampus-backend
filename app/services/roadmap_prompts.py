CREATE_ROADMAP_PROMPT = """
You are an AI learning roadmap planner.
User wants to learn "{selectedTopics}" in {duration} at {skillLevel} skilllevel.
Create a JSON roadmap with 3-5 milestones.
Each milestone has 2-4 topics.
Return ONLY valid JSON in this format:
{{
"milestones": [
{{
"name": "Milestone Name",
"topics": ["Topic 1", "Topic 2", "Topic 3"]
}}
]
}}
"""

TOPIC_EXPLANATION_PROMPT = """
Explain the topic "{topic_name}" in simple language for learning.
Include: what it is, why it's important, and practical examples.
Output in Markdown format.
Keep it concise but informative.
"""