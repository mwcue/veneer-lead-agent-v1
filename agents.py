# agents.py
"""
Agent definitions for the SJ Morse Lead Generation system.

This module initializes agent components for CrewAI, defining their roles,
goals, and tools to identify and analyze potential leads for SJ Morse,
a manufacturer of custom architectural wood veneer panels.
It uses an LLM factory for model agnosticism and client-specific profiles.
"""

import logging
from crewai import Agent
from utils.llm_factory import get_llm_instance
from config import Config # For agent max_iter settings

logger = logging.getLogger(__name__)

def initialize_agents(tools_dict: dict, client_profile: dict):
    """
    Initialize and return all agents needed for the Lead Generation process,
    tailored to the provided client_profile.

    Args:
        tools_dict: Dictionary containing all tool instances.
        client_profile: Dictionary containing client-specific information
                        (name, USPS, target_segments, etc.).

    Returns:
        Dictionary of initialized agents.
    """
    client_name = client_profile.get("CLIENT_NAME", "Our Client")
    logger.info(f"Initializing agents for client: {client_name}...")

    # --- Get LLM instance from factory ---
    logger.info("Attempting to initialize LLM from factory...")
    try:
        agent_llm = get_llm_instance()
        if agent_llm is None:
            logger.critical("Failed to get LLM instance from factory. Agents cannot be initialized.")
            raise ValueError("LLM Initialization Failed via Factory")
        logger.info(f"LLM Factory initialized successfully. LLM Type: {type(agent_llm).__name__}")
    except Exception as e:
        logger.error(f"Error obtaining LLM instance from factory: {e}", exc_info=True)
        raise

    agents = {}
    client_usps_summary = "; ".join(client_profile.get("CORE_PRODUCTS_USPS", ["providing valuable solutions"]))


    # --- 1. Research Agent (Unified but Contextualized) ---
    logger.info(f"Defining Research Agent for {client_name}...")
    agents['research'] = Agent(
        role=f'Lead Sourcing Specialist for {client_name}',
        goal=(
            f"Identify online sources (articles, directories, industry lists, association member pages) "
            f"that list potential B2B clients for {client_name}, a premium manufacturer of "
            f"custom architectural wood veneer panels. Focus on finding companies that match "
            f"pre-defined target segment profiles (e.g., specific types of firms in designated geographic areas)."
        ),
        backstory=(
            f"You are an expert market researcher specializing in B2B lead sourcing for high-value, "
            f"specification-driven products like those offered by {client_name} ({client_usps_summary}). "
            f"Your strength lies in dissecting target segment criteria and finding diverse, reliable online "
            f"sources that enumerate companies fitting these profiles. You are adept at using advanced "
            f"search techniques to uncover relevant company listings."
        ),
        verbose=True,
        allow_delegation=False, # Keep focused
        tools=[tools_dict['web_search'], tools_dict['generic_scraper']],
        llm=agent_llm,
        max_iter=Config.RESEARCH_AGENT_MAX_ITER
    )

    # --- 2. Segment-Specific Analyzer and Reviewer Agents ---
    target_segments = client_profile.get("TARGET_SEGMENTS", [])
    if not target_segments:
        logger.warning(f"No target segments defined in client_profile for {client_name}. No analyzer/reviewer agents will be created.")

    for segment_config in target_segments:
        segment_name = segment_config.get("SEGMENT_NAME")
        if not segment_name:
            logger.warning("Segment found in profile without a name. Skipping agent creation for this segment.")
            continue

        logger.info(f"Defining Analyzer & Reviewer agents for segment: {segment_name}...")

        # --- Analyzer Agent for the Segment ---
        analyzer_agent_key = f"{segment_name}_analyzer"
        segment_geo_focus = segment_config.get("GEOGRAPHIC_FOCUS_TEXT", "relevant geographic areas")
        segment_product_focus = segment_config.get("PRODUCT_FOCUS_FOR_SEGMENT", "custom veneer solutions")
        segment_pain_points_summary = "; ".join(segment_config.get("SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE", ["their specific needs"]))
        
        agents[analyzer_agent_key] = Agent(
            role=f'{segment_name} Prospect Analyzer for {client_name}',
            goal=(
                f"For companies identified as '{segment_name}', find a general contact email and analyze their potential "
                f"business needs and challenges that {client_name} can address with its {segment_product_focus}. "
                f"Focus on pain points such as: {segment_pain_points_summary}. "
                f"The typical geographic focus for this segment is {segment_geo_focus}."
            ),
            backstory=(
                f"You are a specialized B2B analyst with expertise in the '{segment_name}' sector and a deep "
                f"understanding of {client_name}'s offerings ({client_usps_summary}). Your task is to evaluate "
                f"potential leads from this segment, identify their likely operational or project-based pain points "
                f"that align with {client_name}'s solutions, and find an initial point of contact (general email). "
                f"You are skilled at connecting a prospect's implicit needs with tangible product benefits."
            ),
            verbose=True,
            allow_delegation=False,
            tools=[tools_dict['email_finder'], tools_dict['pain_point_analyzer']],
            llm=agent_llm,
            max_iter=Config.ANALYSIS_AGENT_MAX_ITER
        )

        # --- Reviewer Agent for the Segment ---
        reviewer_agent_key = f"{segment_name}_reviewer"
        agents[reviewer_agent_key] = Agent(
            role=f'{segment_name} Lead Quality Reviewer for {client_name}',
            goal=(
                f"Critically review the analyzed pain points for companies in the '{segment_name}' segment. "
                f"Ensure the pain points are specific, relevant to their potential use of {client_name}'s "
                f"custom wood veneer panels, and clearly articulate a value proposition for {client_name}. "
                f"Refine generic statements into actionable insights that highlight {client_name}'s strengths ({client_usps_summary})."
            ),
            backstory=(
                f"You are a meticulous Quality Assurance specialist for B2B lead generation, focusing on the '{segment_name}' sector "
                f"and {client_name}'s market position. You scrutinize analyses to ensure that the identified prospect pain points are not "
                f"superficial but represent genuine opportunities for {client_name} to provide value. Your refinements make "
                f"the lead qualification more robust and the subsequent outreach more effective."
            ),
            verbose=True,
            allow_delegation=False,
            tools=[], # Reviewers primarily use LLM reasoning
            llm=agent_llm,
            max_iter=Config.ANALYSIS_AGENT_MAX_ITER
        )

    logger.info(f"Initialized {len(agents)} agents for {client_name}: {list(agents.keys())}")
    return agents
