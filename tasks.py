# tasks.py
import logging
from crewai import Task, Agent
from config import SJ_MORSE_PROFILE # To provide client context directly in task descriptions

logger = logging.getLogger(__name__)

# --- SEARCH TASKS (Segment-Specific - Assumed to be correct from previous step) ---

def create_search_tasks(research_agent: Agent, segment_config: dict):
    """
    Create tasks for the Research Agent to find sources for a SPECIFIC target segment.
    (Assumed to be correct from previous step)
    """
    segment_name = segment_config.get("SEGMENT_NAME", "Unknown Segment")
    logger.info(f"Creating search tasks for segment: {segment_name}...")

    if not isinstance(research_agent, Agent):
        logger.error(f"Invalid research_agent provided for segment {segment_name}. Cannot create search tasks.")
        return []
    if not segment_config or not isinstance(segment_config, dict):
        logger.error(f"Invalid segment_config provided for segment {segment_name}. Cannot create search tasks.")
        return []

    search_keywords_examples = segment_config.get("SEARCH_KEYWORDS_EXAMPLES", ["general business news"])
    geographic_focus_text = segment_config.get("GEOGRAPHIC_FOCUS_TEXT", "the specified region")
    client_name = SJ_MORSE_PROFILE.get("CLIENT_NAME", "our client")

    plan_search_description = (
        f"Develop a list of 3-5 highly targeted search queries to find online sources "
        f"(articles, lists, directories, industry association member lists) that identify companies "
        f"fitting the profile of '{segment_name}'.\n"
        f"These companies are potential clients for {client_name}, a manufacturer of custom architectural wood veneer panels.\n"
        f"The geographic focus for this segment is: {geographic_focus_text}.\n"
        f"Example search keywords to consider and adapt: {', '.join(search_keywords_examples)}.\n"
        f"Prioritize queries that will find sources listing multiple relevant companies."
    )
    plan_expected_output = (
        "A Python list of 3-5 targeted search query strings specifically designed to find "
        f"sources listing companies within the '{segment_name}' segment, considering the "
        f"geographic focus: {geographic_focus_text}."
    )
    
    execute_search_description = (
        "Execute web searches using the provided list of targeted queries. "
        f"Find the most relevant articles, lists, or directories for the '{segment_name}' segment, "
        f"keeping in mind the geographic focus: {geographic_focus_text}. "
        "Prioritize sources that are likely to list multiple companies fitting this segment profile. "
        "Filter out irrelevant results."
    )
    execute_expected_output = (
        "**CRITICAL:** Your final output MUST be ONLY a Python list of strings, where each string is a unique URL. "
        "Example format: ['https://example.com/list1', 'https://anothersite.org/article', 'https://regionalsource.net/directory']\n"
        "Do NOT include any introductory text, concluding remarks, notes, or any other text before or after the Python list itself. "
        "The output should start directly with '[' and end directly with ']'. Provide up to 10 unique URLs relevant to the search queries."
    )

    try:
        plan_search_task = Task(
            description=plan_search_description,
            expected_output=plan_expected_output,
            agent=research_agent
        )
        execute_search_task = Task(
            description=execute_search_description,
            expected_output=execute_expected_output,
            agent=research_agent,
            context=[plan_search_task]
        )
        logger.debug(f"Search tasks created successfully for segment: {segment_name}")
        return [plan_search_task, execute_search_task]
    except Exception as e:
        logger.error(f"Error creating search tasks for segment {segment_name}: {e}", exc_info=True)
        return []


# --- EXTRACTION TASK (Segment-Aware but General Scraper - Assumed correct) ---

def create_extraction_task(url: str, research_agent: Agent):
    """
    Create a task for the Research Agent to extract company information from a given URL.
    (Assumed to be correct from previous step)
    """
    logger.info(f"Creating extraction task for URL: {url}")
    if not isinstance(research_agent, Agent):
         logger.error(f"Research agent not found or invalid in create_extraction_task for URL {url}. Cannot create task.")
         return None
    if not url or not isinstance(url, str):
        logger.error(f"Invalid URL provided for extraction task: {url}")
        return None

    client_name = SJ_MORSE_PROFILE.get("CLIENT_NAME", "our client")
    extraction_description = (
        f"Use the Generic Scraper tool to scrape the content from the URL: {url}\n"
        f"Analyze the scraped text content to identify companies mentioned. These companies are potential leads for {client_name}.\n"
        "For each company identified, determine their official company name and their primary website URL. "
        "Focus on extracting factual information. Avoid making assumptions about the company's industry "
        "unless explicitly stated on the page.\n"
        "Return the results as a Python list of dictionaries, where each dictionary has 'name' and 'website' keys. "
        "Example: [{'name': 'Acme Corp', 'website': 'https://www.acme.com'}, ...]"
    )
    extraction_expected_output = (
        "A Python list of dictionaries, each containing 'name' and 'website' for companies "
        "identified on the page. If no companies are found, return an empty list. "
        "Format: [{'name': 'Company Name', 'website': 'https://company-website.com'}, ...]"
    )
    try:
        extraction_task = Task(
            description=extraction_description,
            expected_output=extraction_expected_output,
            agent=research_agent
        )
        logger.debug(f"Extraction task created successfully for {url}.")
        return extraction_task
    except Exception as e:
        logger.error(f"Error creating extraction task for {url}: {e}", exc_info=True)
        return None


# --- ANALYSIS TASK (Fully Implemented) ---

def create_analysis_task(company_name: str, company_website: str, analysis_agent: Agent, segment_config: dict, client_profile: dict) -> Task | None:
    """
    Create a task to analyze a company (find email and identify pain points)
    using the provided analysis_agent and contextual information.
    """
    segment_name = segment_config.get("SEGMENT_NAME", "Unknown Segment")
    client_name = client_profile.get("CLIENT_NAME", "Our Client")
    logger.info(f"Creating analysis task for '{company_name}' (Segment: {segment_name}) using agent: {analysis_agent.role if analysis_agent else 'N/A'}")

    if not all([analysis_agent, segment_config, client_profile, company_name, company_website]):
        logger.error(f"Missing required arguments for analysis task creation for {company_name}.")
        return None

    # For the `Company Pain Point Analyzer` tool, we need to pass specific arguments.
    # The agent needs to be instructed to form this input correctly for the tool.
    tool_input_description = (
        "To use the 'Company Pain Point Analyzer' tool, you MUST provide the following inputs to it:\n"
        "- company_name: (string) The name of the company you are analyzing (which is '{company_name}').\n"
        "- segment_config: (dict) The configuration for the '{segment_name}' segment. (The system will provide this to the tool based on your current context).\n"
        "- client_profile: (dict) The profile for {client_name}. (The system will provide this to the tool based on your current context)."
    )
    # Note: In CrewAI, the agent doesn't *literally* construct the dict and pass it.
    # The *framework* handles passing arguments to tools if the tool's `args_schema` is defined
    # or if the LLM is good at structuring its `action_input`.
    # The description above helps the LLM understand *what information is needed by the tool*.
    # The actual passing of complex dicts like segment_config and client_profile to a tool via LLM action_input
    # can be tricky. The tool's `_run` signature `(self, company_name: str, segment_config: dict, client_profile: dict)`
    # means the agent needs to be prompted to *know* that these are available or that it should invoke the tool
    # in a way that these are implicitly passed (if the framework supports it well for complex objects) or by providing
    # the key pieces of information from those dicts directly in its thought process for the tool.

    # For now, the `PainPointAnalyzerTool` in `llm_tools.py` directly accepts these dicts.
    # The agent's execution of the task will call the tool. CrewAI's execution layer
    # will need to map the agent's decision to call the tool with the parameters.
    # The description primes the agent.

    analysis_task_description = (
        f"Your mission is to analyze the company '{company_name}' (Website: {company_website}). "
        f"This company is categorized under the '{segment_name}' segment and is a potential client for {client_name}.\n\n"
        f"Follow these steps:\n"
        f"1.  **Find Contact Email:** Use the 'Unified Email Finder' tool with the company's website ('{company_website}') to find a general contact email address (e.g., info@, sales@, contact@). Prioritize non-personal, role-based, or departmental emails if available.\n\n"
        f"2.  **Analyze Pain Points:** Use the 'Company Pain Point Analyzer' tool. "
        f"You will need to provide it with the company's name ('{company_name}'), the segment configuration for '{segment_name}', and the client profile for '{client_name}'. "
        f"The tool will help identify 3-5 specific business pain points or opportunities this company likely faces that {client_name} (a premium manufacturer of custom architectural wood veneer panels) can address. "
        f"Focus on challenges relevant to their potential need for {client_name}'s products/services.\n\n"
        f"3.  **Format Output:** Combine the findings into a single, structured response. "
        f"Start with 'Contact Email:' followed by the email found (or 'Email not found.'). "
        f"Then, on a new line, start with 'Pain Points:' followed by the numbered or bulleted list of 3-5 pain points provided by the 'Company Pain Point Analyzer' tool."
    )

    analysis_expected_output = (
        "A structured response. It MUST start with 'Contact Email:' followed by the email address (or 'Email not found.').\n"
        "On a new line, it MUST start with 'Pain Points:' followed by a numbered or bulleted list of 3-5 specific pain points. "
        "Example:\n"
        "Contact Email: info@examplecontractors.com\n"
        "Pain Points:\n"
        "1. Difficulty meeting tight project deadlines due to unreliable material suppliers for specialized veneer.\n"
        "2. Challenges ensuring consistent AWI Premium Grade quality for veneer panels across large-scale projects.\n"
        "3. High costs associated with on-site adjustments for veneer panels that are not cut-to-size accurately."
    )

    try:
        analysis_task = Task(
            description=analysis_task_description,
            expected_output=analysis_expected_output,
            agent=analysis_agent,
            # Tools are defined at the agent level, but specifying them here can sometimes help the LLM focus.
            # However, it's generally better if the agent knows its tools from its definition.
            # tools=[tools_dict['email_finder'], tools_dict['pain_point_analyzer']] # Optional: if agent has many tools
        )
        logger.debug(f"Analysis task created successfully for {company_name} ({segment_name})")
        return analysis_task
    except Exception as e:
        logger.error(f"Error creating analysis task for {company_name}: {e}", exc_info=True)
        return None


# --- REVIEW TASK (Fully Implemented) ---

def create_review_task(company_name: str, company_website: str, initial_pain_points: str, review_agent: Agent, segment_config: dict, client_profile: dict) -> Task | None:
    """
    Create a task to review and refine initially generated pain points
    using the provided review_agent and contextual information.
    """
    segment_name = segment_config.get("SEGMENT_NAME", "Unknown Segment")
    client_name = client_profile.get("CLIENT_NAME", "Our Client")
    logger.info(f"Creating review task for '{company_name}' (Segment: {segment_name}) using agent: {review_agent.role if review_agent else 'N/A'}")

    if not all([review_agent, segment_config, client_profile, company_name, company_website, initial_pain_points is not None]): # initial_pain_points can be empty string
        logger.error(f"Missing required arguments for review task creation for {company_name}.")
        return None

    client_usps_summary = "; ".join(client_profile.get("CORE_PRODUCTS_USPS", ["providing valuable solutions"]))
    segment_pain_examples_summary = "; ".join(segment_config.get("SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE", ["their specific needs"]))

    # Ensure initial_pain_points is formatted clearly if it's a multi-line string
    formatted_initial_points = "\n".join([f"  - {line.strip()}" for line in initial_pain_points.split('\n') if line.strip()])
    if not formatted_initial_points:
        formatted_initial_points = "  - No specific initial pain points were provided or extracted clearly."

    review_task_description = (
        f"**You are a Senior Lead Qualification Analyst for {client_name}.**\n"
        f"{client_name} specializes in: {client_usps_summary}.\n\n"
        f"**Company Under Review:** '{company_name}' (Website: {company_website})\n"
        f"**Segment:** '{segment_name}' (Typical segment challenges that {client_name} addresses: {segment_pain_examples_summary})\n\n"
        f"**Initial Pain Points Submitted for Review:**\n{formatted_initial_points}\n\n"
        f"**Your Critical Review Objectives:**\n"
        f"1.  **Validate Specificity & Relevance:** Scrutinize each initial pain point. Is it concrete and directly related to the challenges a '{segment_name}' company would face concerning architectural wood veneer panels? Does it avoid generic business platitudes?\n"
        f"2.  **Align with {client_name}'s Solutions:** Does each point clearly highlight a problem that {client_name}'s specific products (e.g., AWI Premium Grade panels, custom CNC work, reliable regional delivery, cut-to-size services) can solve effectively? The connection must be obvious.\n"
        f"3.  **Refine or Reject:**\n"
           f"*   If a point is too vague (e.g., 'improve material sourcing'), REFINE it into a specific, compelling problem (e.g., 'Experiences inconsistent quality and long lead times when sourcing specialized veneers, impacting project schedules and finish standards.').\n"
           f"*   If a point is irrelevant to {client_name}'s veneer business or unfixably generic, REJECT it and explain briefly in your thought process (not in the final output list). Aim to replace rejected points if possible to maintain 3-5 quality points.\n"
        f"4.  **Ensure Actionability:** The refined pain points should give the sales team a clear angle for approaching '{company_name}'.\n\n"
        f"**Final Output Requirements:**\n"
        f"Produce ONLY a numbered list of 3-5 **final, high-quality, refined or validated pain points**. "
        f"Each point must be a compelling reason for '{company_name}' to consider {client_name} for their architectural wood veneer needs. "
        f"Do NOT include your reasoning or any text other than the final list itself. Start directly with '1.'."
    )

    review_expected_output = (
        "A final, refined list of 3-5 specific business pain points for the company, "
        f"clearly relevant to the '{segment_name}' segment and demonstrating how {client_name}'s "
        "custom architectural wood veneer panels can provide a solution. "
        "The output should be ONLY a numbered or bulleted list. "
        "Example:\n"
        "1. Consistent difficulty in sourcing specific exotic veneers that meet both aesthetic requirements and AWI Premium Grade standards for high-end hospitality projects.\n"
        "2. Project delays and budget overruns due to inconsistencies or damage in veneer panels sourced from multiple, less reliable suppliers.\n"
        "3. Limited in-house capacity for precise cut-to-size and edge-banding of veneer panels, increasing on-site labor costs and waste."
    )

    try:
        review_task = Task(
            description=review_task_description,
            expected_output=review_expected_output,
            agent=review_agent
            # No tools typically assigned to reviewer agent, it relies on LLM reasoning.
        )
        logger.debug(f"Review task created successfully for {company_name} ({segment_name})")
        return review_task
    except Exception as e:
        logger.error(f"Error creating review task for {company_name}: {e}", exc_info=True)
        return None

