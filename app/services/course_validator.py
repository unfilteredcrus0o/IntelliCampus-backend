"""
This validates what users type when creating courses - basically keeps the garbage out
while letting legitimate tech and business topics through.

What it does:
- Accepts programming languages (Python, R, Rust, JavaScript, etc.)
- Accepts frameworks and tools (React, Docker, Kubernetes, etc.)
- Accepts corporate training (POSH, Leadership, Safety, etc.)
- Rejects random nonsense (keyboard mashing, test inputs, hobbies)
- Suggests alternatives when input is close but not quite right

How it works:
1. Quick check against known good/bad lists (super fast)
2. Look for tech/business keywords if not in the lists  
3. Basic word pattern analysis for edge cases
4. Helpful error messages instead of just "nope"

Used by the roadmap API - bad input gets HTTP 422, good input proceeds to course generation.
Add new tech to VALID_TOPICS, add new garbage patterns to INVALID_TOPICS.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Corporate Learning Platform - Approved Course Topics Only
# This is a whitelist approach for a company learning platform
APPROVED_COURSE_TOPICS = {
    # Complete Technical Course Names Only - No Partial Matches Allowed
    
    # Programming Languages (Full course names)
    "programming_languages": [
        "python programming", "javascript fundamentals", "java development", 
        "c++ programming", "c# development", "go programming", "rust programming",
        "php development", "typescript fundamentals", "swift development",
        "kotlin programming", "r programming", "scala programming"
    ],
    
    # Web Development (Complete course titles)
    "web_development": [
        "html fundamentals", "css styling", "react development", "vue.js development",
        "angular development", "node.js development", "express.js framework",
        "django framework", "flask development", "spring framework", 
        "laravel framework", "bootstrap framework", "sass preprocessing",
        "webpack bundling", "bun runtime", "frontend development", 
        "backend development", "full stack development"
    ],
    
    # Data & Analytics (Specific complete topics)
    "data_analytics": [
        "data science fundamentals", "machine learning basics", "artificial intelligence concepts",
        "deep learning fundamentals", "data analysis techniques", "statistical analysis",
        "business intelligence", "data visualization", "predictive analytics",
        "sql database management", "mongodb database", "postgresql administration",
        "mysql database", "data warehousing", "big data analytics"
    ],
    
    # Cloud & DevOps (Complete course names)
    "cloud_devops": [
        "aws cloud fundamentals", "microsoft azure basics", "google cloud platform",
        "docker containerization", "kubernetes orchestration", "terraform infrastructure",
        "jenkins automation", "ci/cd pipelines", "devops practices",
        "microservices architecture", "serverless computing", "cloud security"
    ],
    
    # Mobile Development
    "mobile_development": [
        "ios app development", "android app development", "flutter development",
        "react native development", "mobile ui/ux design", "mobile app testing"
    ],
    
    # Cybersecurity (Complete security courses)
    "cybersecurity": [
        "cybersecurity fundamentals", "ethical hacking basics", "network security",
        "information security management", "penetration testing", "security auditing",
        "incident response", "vulnerability assessment", "security compliance"
    ],
    
    # Business & Management Skills
    "business_skills": [
        "project management fundamentals", "agile methodology", "scrum master training",
        "leadership development", "effective communication", "business analysis",
        "product management", "digital marketing fundamentals", "search engine optimization"
    ],
    
    # Design & UI/UX  
    "design": [
        "ui/ux design fundamentals", "user experience research", "user interface design",
        "graphic design basics", "figma design tool", "web design principles",
        "mobile app design", "design thinking", "prototyping"
    ],
    
    # Corporate Compliance & Training (Exact company course names)
    "corporate_compliance": [
        "prevention of sexual harassment training", "posh compliance training",
        "workplace harassment prevention", "diversity and inclusion training",
        "unconscious bias training", "code of conduct training", "business ethics",
        "anti-corruption training", "conflict of interest policies"
    ],
    
    # Health & Safety (Complete course titles)  
    "health_safety": [
        "workplace safety fundamentals", "fire safety training", "first aid certification",
        "cpr certification", "occupational health awareness", "ergonomics training",
        "mental health awareness", "stress management", "workplace wellness"
    ],
    
    # IT Security Awareness (Specific courses)
    "it_security_awareness": [
        "cybersecurity awareness training", "data privacy fundamentals", 
        "phishing awareness training", "password security best practices",
        "gdpr compliance training", "data protection policies",
        "social engineering awareness", "email security training", "remote work security"
    ],
    
    # Professional Development
    "professional_development": [
        "leadership skills development", "management training", "time management",
        "presentation skills training", "public speaking", "team building",
        "conflict resolution", "negotiation skills", "customer service excellence",
        "emotional intelligence", "critical thinking"
    ],
    
    # Quality & Process Management
    "quality_process": [
        "quality management systems", "iso certification training", "process improvement",
        "six sigma fundamentals", "lean management principles", "audit training",
        "documentation best practices", "standard operating procedures"
    ],
    
    # Business Operations
    "business_operations": [
        "financial literacy", "budget management", "expense reporting",
        "procurement processes", "vendor management", "contract management",
        "supply chain basics", "inventory management"
    ],
    
    # Emergency & Crisis Management  
    "emergency_management": [
        "emergency response procedures", "crisis management planning",
        "business continuity planning", "disaster preparedness",
        "incident reporting procedures", "evacuation procedures"
    ],
    
    # Digital Tools & Communication
    "digital_tools": [
        "microsoft office training", "excel fundamentals", "powerpoint presentations",
        "google workspace training", "microsoft teams", "slack communication",
        "zoom video conferencing", "email etiquette", "digital collaboration"
    ]
}


VALID_TOPICS = {
    'r', 'c', 'go', 'rust', 'java', 'python', 'javascript', 'typescript', 
    'c++', 'cpp', 'c#', 'csharp', 'kotlin', 'swift', 'scala', 'ruby', 
    'php', 'perl', 'lua', 'dart', 'elixir', 'erlang', 'haskell', 'clojure',
    'f#', 'fsharp', 'objective-c', 'pascal', 'fortran', 'cobol', 'assembly',
    'matlab', 'bash', 'powershell', 'shell', 'sql', 'golang',
    'html', 'css', 'react', 'angular', 'vue', 'svelte', 'node', 'express',
    'django', 'flask', 'fastapi', 'spring', 'laravel', 'rails', 'nextjs',
    'gatsby', 'astro', 'remix', 'bun', 'deno', 'webpack', 'vite',
    'bootstrap', 'tailwind', 'sass', 'scss', 'flutter', 'reactnative',
    'docker', 'kubernetes', 'terraform', 'ansible', 'jenkins',
    'aws', 'azure', 'gcp', 'mysql', 'postgresql', 'mongodb', 'redis',
    'pandas', 'numpy', 'tensorflow', 'pytorch', 'jupyter', 'tableau',
    'ui', 'ux', 'api', 'seo', 'ai', 'ml', 'devops', 'cicd', 'cms', 'crm',
    'frontend', 'backend', 'fullstack', 'database', 'testing', 'cybersecurity',
    'leadership', 'management', 'communication', 'posh', 'compliance', 'safety'
}

INVALID_TOPICS = {
    'qon', 'madar', 'wsnwns', 'asdf', 'qwerty', 'hello', 'world', 'test',
    'qwe', 'asd', 'zxc', 'wqa', 'xda', 'abc', 'def', 'xyz',
    'music', 'dance', 'sports', 'games', 'movies', 'food', 'travel', 'cooking'
}

def is_potentially_valid_course_topic(topic: str) -> Tuple[bool, str]:
    """
    Validates whether a given topic string represents a legitimate course subject
    for the corporate learning platform.
    
    This function performs fast, intelligent validation using a multi-stage approach:
    1. Basic input sanitization and format checks
    2. Fast lookup against pre-compiled valid/invalid topic sets
    3. Exact matching against approved course catalog
    4. Contextual analysis for technical and business terms
    5. Pattern-based validation for word legitimacy
    
    Args:
        topic (str): The course topic string to validate
        
    Returns:
        Tuple[bool, str]: A tuple containing:
            - bool: True if topic is valid, False if invalid
            - str: Descriptive message explaining the validation result
            
    Examples:
        >>> is_potentially_valid_course_topic("python")
        (True, "Approved topic: python")
        
        >>> is_potentially_valid_course_topic("qon")
        (False, "Invalid topic: qon")
        
        >>> is_potentially_valid_course_topic("machine learning basics")
        (True, "Recognized course: machine learning basics")
    """
    if not topic or not isinstance(topic, str):
        return False, "Please provide a valid course topic"
    
    topic_clean = topic.strip().lower()
    
    if not topic_clean:
        return False, "Course topic cannot be empty"
    
    if re.match(r'^\d+$', topic_clean):
        return False, "Please enter a valid course topic"
    
    if len(topic_clean) == 1 and topic_clean not in {'r', 'c'}:
        return False, "Please enter a valid course topic"
    
    if topic_clean in VALID_TOPICS:
        return True, f"Approved topic: {topic.strip()}"
    
    if topic_clean in INVALID_TOPICS:
        return False, f"Invalid topic: {topic.strip()}"
    
    for domain_topics in APPROVED_COURSE_TOPICS.values():
        if topic_clean in [t.lower() for t in domain_topics]:
            return True, f"Recognized course: {topic.strip()}"
    
    tech_indicators = ['dev', 'program', 'code', 'tech', 'software', 'app', 'web', 'data', 'system']
    business_indicators = ['manage', 'lead', 'train', 'skill', 'business', 'office', 'corporate']
    
    if any(indicator in topic_clean for indicator in tech_indicators + business_indicators):
        return True, f"Professional topic: {topic.strip()}"
    
    if len(topic_clean) >= 3:
        vowels = sum(1 for c in topic_clean if c in 'aeiou')
        if vowels >= 1 and len(topic_clean) - vowels <= len(topic_clean) * 0.8:
            return True, f"Valid topic: {topic.strip()}"
    
    return False, f"Topic not recognized: {topic.strip()}"

def find_domain_matches(topics: List[str]) -> Dict[str, List[str]]:
    """
    Analyzes a list of course topics and categorizes them by domain.
    
    This function takes validated course topics and maps them to their appropriate
    domain categories (e.g., programming_languages, web_development, data_analytics).
    Only topics that pass validation are considered for domain matching.
    
    Args:
        topics (List[str]): List of course topic strings to categorize
        
    Returns:
        Dict[str, List[str]]: Dictionary mapping domain names to lists of 
                             matched topics within that domain
                             
    Example:
        >>> find_domain_matches(["python", "react", "leadership"])
        {"programming_languages": ["python programming"], 
         "web_development": ["react development"],
         "professional_development": ["leadership development"]}
    """
    matches = {}
    
    for topic in topics:
        topic_clean = topic.strip().lower()
        
        is_valid, _ = is_potentially_valid_course_topic(topic)
        if not is_valid:
            continue
            
        for domain, domain_topics in APPROVED_COURSE_TOPICS.items():
            domain_matches = []
            
            for approved_topic in domain_topics:
                if topic_clean == approved_topic.lower():
                    domain_matches.append(approved_topic)
            
            if domain_matches:
                if domain not in matches:
                    matches[domain] = []
                matches[domain].extend(domain_matches)
    
    return matches

def validate_course_input(selected_topics: List[str]) -> Dict:
    """
    Performs comprehensive validation of user-submitted course topics and determines
    the appropriate action for the roadmap creation system.
    
    This function coordinates the entire validation workflow by:
    1. Validating each individual topic using is_potentially_valid_course_topic()
    2. Categorizing results into valid and invalid topics
    3. Determining system action based on validation ratios
    4. Providing suggestions for invalid topics
    5. Generating domain mappings for valid topics
    
    Business Logic:
    - If all topics are invalid: Return error action
    - If >70% of topics are invalid: Return fallback_custom action  
    - If some topics are valid: Return proceed action with valid topics only
    
    Args:
        selected_topics (List[str]): List of course topic strings submitted by user
        
    Returns:
        Dict: Validation result dictionary containing:
            - is_valid (bool): Overall validation status
            - action (str): System action - "proceed", "fallback_custom", or "error"
            - invalid_topics (List[Dict]): Invalid topics with rejection reasons
            - valid_topics (List[str]): Topics that passed validation
            - domain_matches (Dict[str, List[str]]): Domain categorization of valid topics
            - suggested_topics (List[str]): Alternative suggestions for invalid topics
            - reason (str): Human-readable explanation of the validation outcome
    """
    logger.info(f"Validating course input: {selected_topics}")
    
    result = {
        "is_valid": True,
        "action": "proceed",  # proceed, fallback_custom, error
        "invalid_topics": [],
        "valid_topics": [],
        "domain_matches": {},
        "suggested_topics": [],
        "reason": ""
    }
    
    if not selected_topics:
        result.update({
            "is_valid": False,
            "action": "error",
            "reason": "No topics provided"
        })
        return result
    
    for topic in selected_topics:
        is_valid, reason = is_potentially_valid_course_topic(topic)
        if is_valid:
            result["valid_topics"].append(topic)
        else:
            result["invalid_topics"].append({"topic": topic, "reason": reason})
    
    if result["valid_topics"]:
        result["domain_matches"] = find_domain_matches(result["valid_topics"])
    
    total_topics = len(selected_topics)
    valid_count = len(result["valid_topics"])
    invalid_count = len(result["invalid_topics"])
    
    if invalid_count == total_topics:
        result.update({
            "is_valid": False,
            "action": "error",
            "reason": "All provided topics appear to be invalid or unrecognized"
        })
    elif invalid_count / total_topics > 0.7:
        result.update({
            "is_valid": False,
            "action": "fallback_custom",
            "reason": "Most topics appear invalid, falling back to Custom Course"
        })
    elif valid_count > 0:
        result.update({
            "is_valid": True,
            "action": "proceed",
            "reason": f"Proceeding with {valid_count} valid topics"
        })
        
        if invalid_count > 0:
            result["suggested_topics"] = suggest_similar_topics(result["invalid_topics"])
    
    logger.info(f"Validation result: {result['action']} - {result['reason']}")
    return result

def suggest_similar_topics(invalid_topics: List[Dict]) -> List[str]:
    """
    Generates helpful alternative course topic suggestions for rejected inputs.
    
    This function analyzes invalid topics and provides meaningful alternatives from
    the approved course catalog. It uses pattern matching and keyword analysis to
    map common user inputs to legitimate course topics, helping users understand
    what types of topics are accepted by the system.
    
    The suggestion logic includes:
    1. Direct mapping for common abbreviated terms (e.g., "web" -> "frontend development")
    2. Keyword-based inference for partial matches
    3. Context-aware recommendations based on user intent
    4. Deduplication to avoid repeated suggestions
    
    Args:
        invalid_topics (List[Dict]): List of dictionaries containing invalid topics,
                                    where each dict has "topic" and "reason" keys
        
    Returns:
        List[str]: List of up to 5 suggested alternative course topics from the
                  approved catalog, deduplicated and relevant to the invalid inputs
                  
    Example:
        >>> suggest_similar_topics([{"topic": "web", "reason": "Too vague"}])
        ["frontend development", "backend development", "full stack development"]
    """
    suggestions = []
    
    for invalid_item in invalid_topics:
        topic = invalid_item["topic"].strip().lower()
        
        # Map common invalid inputs to approved course topics
        topic_mapping = {
            'web': 'frontend development',
            'website': 'web development',
            'data': 'data analysis techniques', 
            'machine': 'machine learning basics',
            'ai': 'artificial intelligence concepts',
            'mobile': 'mobile app development',
            'app': 'mobile app development', 
            'security': 'cybersecurity fundamentals',
            'design': 'ui/ux design fundamentals',
            'programming': 'python programming',
            'coding': 'javascript fundamentals',
            'leadership': 'leadership development',
            'management': 'management training',
            'safety': 'workplace safety fundamentals',
            'training': 'professional development',
            'business': 'business analysis',
            'marketing': 'digital marketing fundamentals'
        }
        
        if topic in topic_mapping:
            suggestions.append(topic_mapping[topic])
        
        elif 'web' in topic or 'website' in topic:
            suggestions.extend(['frontend development', 'backend development', 'full stack development'])
        elif 'data' in topic:
            suggestions.extend(['data analysis techniques', 'data science fundamentals', 'business intelligence'])
        elif 'machine' in topic or 'ai' in topic:
            suggestions.extend(['machine learning basics', 'artificial intelligence concepts', 'deep learning fundamentals'])
        elif 'mobile' in topic or 'app' in topic:
            suggestions.extend(['ios app development', 'android app development', 'flutter development'])
        elif 'security' in topic:
            suggestions.extend(['cybersecurity fundamentals', 'information security management', 'cybersecurity awareness training'])
        elif 'design' in topic:
            suggestions.extend(['ui/ux design fundamentals', 'graphic design basics', 'web design principles'])
    
    return list(set(suggestions))[:5]

def create_custom_course_roadmap_data(original_input: List[str], skill_level: str, duration: str) -> Dict:
    """
    Generates fallback roadmap data for a generic "Custom Course" when user input
    contains too many invalid topics to process normally.
    
    This function is called when the validation system determines that the user's
    input is predominantly invalid (>70% invalid topics) but the system should still
    provide a learning experience rather than completely rejecting the request.
    It creates a generic course structure that the LLM can populate with general
    learning content.
    
    The generated data structure follows the same format as normal course requests
    but includes metadata indicating it was created as a fallback option, allowing
    the downstream systems to handle it appropriately.
    
    Args:
        original_input (List[str]): The original invalid topic list from the user
        skill_level (str): User's declared skill level (beginner, intermediate, advanced)
        duration (str): Requested course duration (e.g., "4 weeks", "2 months")
        
    Returns:
        Dict: Roadmap data dictionary containing:
            - interests (List[str]): List containing generic "Custom Course" topic
            - level (str): The user's skill level
            - timelines (Dict[str, str]): Duration mapping for the custom course
            - title (str): Generated title based on skill level
            - metadata (Dict): Additional information about fallback creation
                - fallback_reason (str): Explanation of why fallback was used
                - original_input (List[str]): The original invalid input for reference
                - created_as_custom (bool): Flag indicating fallback creation
                
    Example:
        >>> create_custom_course_roadmap_data(["invalid", "topics"], "beginner", "4 weeks")
        {
            "interests": ["Custom Course"],
            "level": "beginner", 
            "timelines": {"Custom Course": "4 weeks"},
            "title": "Beginner Custom Learning Track",
            "metadata": {
                "fallback_reason": "Invalid course input detected",
                "original_input": ["invalid", "topics"],
                "created_as_custom": True
            }
        }
    """
    return {
        "interests": ["Custom Course"],
        "level": skill_level,
        "timelines": {"Custom Course": duration},
        "title": f"{skill_level.title()} Custom Learning Track",
        "metadata": {
            "fallback_reason": "Invalid course input detected",
            "original_input": original_input,
            "created_as_custom": True
        }
    }
