CREATE_ROADMAP_TITLE_PROMPT = """
You are an expert educational content creator specializing in creating engaging, professional course titles.

**Task**: Generate a compelling, professional title for a learning roadmap with the following parameters:
- **Topics**: {selectedTopics}
- **Skill Level**: {skillLevel}
- **Duration**: {duration}

**Guidelines**:
1. Create a title that is professional yet engaging
2. Reflect the skill level appropriately
3. Keep it concise but descriptive (4-8 words ideal)
4. Avoid generic terms like "Learning Path" or "Course"
5. Make it sound like a real professional certification or bootcamp

**Examples of good titles**:
- "Advanced Python Web Development Mastery"
- "React & Node.js Full-Stack Bootcamp"
- "Data Science with Machine Learning Fundamentals"
- "DevOps Engineering Professional Track"

**Output**: Return ONLY the title text, no quotes, no additional explanation.
"""

CREATE_ROADMAP_PROMPT = """
You are an expert curriculum designer and learning strategist with deep knowledge across all educational domains.

**Learning Goal**: Create a comprehensive roadmap for "{selectedTopics}" over {duration} for a {skillLevel} level learner.

**Your Task**: Design a progressive learning path that maximizes educational effectiveness and learner engagement.

**Guidelines by Skill Level**:
- **Beginner**: Start with foundational concepts, use simple language, include lots of practice
- **Intermediate**: Build on existing knowledge, introduce advanced concepts gradually  
- **Advanced**: Focus on mastery, optimization, real-world applications, and cutting-edge developments

**Timeline Considerations**:
- Break down the {duration} effectively across milestones
- Ensure realistic pacing for the skill level
- Include time for practice and reinforcement

**Requirements**:
1. Create 3-5 progressive milestones that build logically
2. Each milestone should have 2-4 specific, actionable topics
3. Topics must be measurable and have clear learning outcomes
4. Consider prerequisite relationships between topics
5. Include both theoretical understanding and practical application

**Output Format** - Return ONLY this JSON structure:
{{
  "milestones": [
    {{
      "name": "Descriptive milestone name (no 'Milestone X:' prefix)",
      "description": "What the learner will achieve by completing this milestone",
      "topics": [
        "Specific, actionable topic name",
        "Another specific topic name"
      ],
      "estimated_duration": "realistic time estimate for this milestone"
    }}
  ],
  "overall_difficulty_progression": "brief description of how difficulty increases",
  "success_criteria": "how learners will know they've mastered the subject"
}}

**Quality Standards**:
- Topics should be specific, not generic
- Each milestone should represent meaningful progress
- Learning path should be logical and pedagogically sound
- Consider different learning styles and preferences

Return ONLY valid JSON - no additional text or explanation.
"""

TOPIC_EXPLANATION_PROMPT = """
You are a world-class educator creating premium learning content for the topic: "{topic_name}"

**Your Mission**: Create an exceptional explanation that transforms confusion into clarity and builds genuine understanding.

**Content Requirements**:

1. **Hook the Learner** (Opening)
   - Start with why this topic matters
   - Use a relatable analogy or real-world connection
   - Create curiosity and motivation

2. **Build Understanding** (Core Content)
   - Break complex ideas into digestible parts
   - Use the "explain like I'm 5" approach when needed
   - Include concrete examples and analogies
   - Address common misconceptions

3. **Make it Practical** (Application)
   - Show real-world applications
   - Provide actionable steps
   - Include practice suggestions
   - Connect to learner's goals

4. **Support Success** (Guidance)
   - Highlight common pitfalls and how to avoid them
   - Provide troubleshooting tips
   - Suggest additional resources for deeper learning
   - Include self-assessment questions

**Response Format** - Return as JSON:
{{
  "content": "# {topic_name}\\n\\n## Why This Matters\\n\\n[Compelling introduction]\\n\\n## Understanding the Fundamentals\\n\\n[Core explanation with examples]\\n\\n## Real-World Applications\\n\\n[Practical uses and examples]\\n\\n## Step-by-Step Learning Approach\\n\\n[How to master this topic]\\n\\n## Common Challenges & Solutions\\n\\n[What learners struggle with]\\n\\n## Practice & Next Steps\\n\\n[Actionable practice suggestions]\\n\\n## Self-Check Questions\\n\\n[Questions to test understanding]",
  "difficulty_level": "beginner|intermediate|advanced",
  "estimated_time": "realistic learning time",
  "prerequisites": ["prerequisite topic 1", "prerequisite topic 2"],
  "key_concepts": ["core concept 1", "core concept 2", "core concept 3"],
  "practical_applications": ["real-world use 1", "real-world use 2"],
  "learning_objectives": ["specific skill 1", "specific skill 2"]
}}

**Quality Standards**:
- Minimum 400 words in content
- Use engaging, conversational tone
- Include specific, concrete examples
- Structure with clear markdown headers
- Make complex concepts accessible
- Ensure practical value for learners

Return ONLY valid JSON - no additional text.
"""

GENERATE_TOPIC_SOURCES_PROMPT = """
You are an expert research librarian and educational resource curator with comprehensive knowledge of learning materials across all subjects.

**Topic**: "{topic_name}"

**Your Task**: Find and recommend the highest quality, most credible learning resources for this topic.

**Source Categories to Consider**:
**Academic**: University courses, MOOCs, educational institutions
**Official Documentation**: Authoritative references, standards, official guides  
**Video Learning**: Educational YouTube channels, tutorial series, course platforms
**Books & Publications**: Well-regarded textbooks, industry publications
**Interactive**: Hands-on platforms, coding environments, simulators
**Articles**: High-quality blog posts, industry insights, case studies

**Quality Criteria**:
**Authority**: Created by recognized experts or institutions
**Accuracy**: Factual, up-to-date information
**Accessibility**: Free or affordable access
**Educational Value**: Specifically designed for learning
**Community**: Active community or good reviews

**Research Process**:
1. Identify the most authoritative sources for this topic
2. Find diverse resource types (video, text, interactive)
3. Ensure sources cater to different learning preferences
4. Verify URLs are real and accessible
5. Prioritize free/open educational resources

**Output Format** - Return as JSON array:
[
  {{
    "title": "Exact title of the resource",
    "url": "https://complete-valid-url.com/path",
    "description": "Detailed explanation of why this source is excellent for learning {topic_name}. What specific educational value does it provide?",
    "source_type": "documentation|course|video|book|interactive|article",
    "difficulty_level": "beginner|intermediate|advanced|mixed",
    "estimated_time": "time to complete this resource",
    "credibility_score": 8,
    "is_free": true,
    "last_updated": "approximate last update time"
  }}
]

**Critical Requirements**:
ALL URLs must be real, valid, and accessible
Include 5-7 diverse, high-quality sources
Focus on educational value and learner outcomes
Prioritize authoritative and well-maintained resources

Return ONLY valid JSON array - no additional text or explanation.
"""

VALIDATE_SOURCES_PROMPT = """
You are a fact-checker and educational quality assurance expert.

**Task**: Validate and enhance these learning sources for the topic "{topic_name}"

**Sources to Validate**:
{sources_json}

**Validation Criteria**:
1. **URL Legitimacy**: Does the URL look real and educational?
2. **Source Authority**: Is this from a credible educational source?
3. **Relevance**: How well does this relate to the topic?
4. **Educational Value**: Will this actually help learners?
5. **Accessibility**: Is this resource accessible to most learners?

**Enhancement Tasks**:
- Improve descriptions to be more helpful for learners
- Adjust credibility scores based on source authority
- Remove any questionable or irrelevant sources
- Add missing metadata where possible

**Output Format** - Return enhanced sources as JSON:
{{
  "validated_sources": [
    {{
      "title": "Enhanced title if needed",
      "url": "verified URL",
      "description": "Enhanced description focusing on learner value",
      "source_type": "updated type if needed",
      "credibility_score": "adjusted score 1-10",
      "validation_notes": "brief note on why this source is valuable"
    }}
  ],
  "removed_sources": [
    {{
      "title": "removed source title",
      "reason": "why it was removed"
    }}
  ]
}}

Return ONLY valid JSON.
"""

ENHANCE_EXPLANATION_PROMPT = """
You are an educational content improvement specialist and learning science expert.

**Current Explanation**: "{current_explanation}"
**Topic**: "{topic_name}"

**Your Task**: Significantly enhance this explanation to make it more engaging, comprehensive, and educationally effective.

**Enhancement Areas**:

**Clarity & Structure**
- Improve logical flow and organization
- Add clear section headers and transitions
- Break down complex concepts into simpler parts

**Engagement & Accessibility**  
- Add compelling analogies and metaphors
- Include relevant real-world examples
- Use conversational, encouraging tone
- Address different learning styles

**Practical Value**
- Add hands-on exercises or thought experiments
- Include step-by-step guidance
- Provide troubleshooting tips
- Connect to broader learning goals

**Learning Science**
- Use spaced repetition concepts
- Include self-assessment opportunities  
- Add memory aids and mnemonics
- Structure for progressive difficulty

**Output Format** - Return as JSON:
{{
  "enhanced_content": "# {topic_name}\\n\\n[Significantly improved markdown content with better structure, examples, and educational value]",
  "improvement_notes": "brief summary of key enhancements made",
  "quality_score": 85,
  "educational_techniques_used": ["technique 1", "technique 2"]
}}

**Quality Standards**:
- Minimum 500 words of substantive content
- Include at least 3 concrete examples
- Use proper markdown formatting
- Ensure content is engaging and memorable
- Make abstract concepts tangible

Return ONLY valid JSON.
"""

CONTEXT_AWARE_EXPLANATION_PROMPT = """
You are an adaptive educational AI that personalizes learning content.

**Topic**: "{topic_name}"
**Learner Context**:
- Skill Level: {skill_level}
- Learning Goals: {learning_goals}
- Time Available: {time_available}
- Previous Topics Completed: {completed_topics}

**Your Task**: Create a personalized explanation that adapts to this learner's specific context and needs.

**Personalization Factors**:
- **Skill Level Adaptation**: Adjust complexity and prerequisites
- **Goal Alignment**: Connect content to learner's specific objectives
- **Time Optimization**: Structure content for available time
- **Prior Knowledge**: Build on what they've already learned

**Content Structure**:
1. **Personalized Introduction** - Reference their goals and context
2. **Adapted Core Content** - Appropriate complexity for their level
3. **Contextual Examples** - Examples relevant to their goals
4. **Personalized Practice** - Suggestions based on their timeline
5. **Custom Next Steps** - Tailored progression recommendations

**Response Format**:
{{
  "personalized_content": "[Customized markdown explanation]",
  "adaptation_notes": "how content was personalized for this learner",
  "recommended_focus_areas": ["area 1", "area 2"],
  "time_breakdown": {{
    "theory": "X minutes",
    "practice": "X minutes", 
    "review": "X minutes"
  }}
}}

Return ONLY valid JSON with content adapted specifically for this learner's context.
"""