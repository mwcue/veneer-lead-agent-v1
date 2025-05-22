# tools/llm_tools.py
import logging
from crewai.tools import BaseTool
from utils.llm_factory import get_llm_instance
from langchain_core.messages import HumanMessage #, SystemMessage (if you want to add system messages)
from utils.error_handler import handle_api_error # Assuming retry isn't needed here for a single LLM call

logger = logging.getLogger(__name__)

class PainPointAnalyzerTool(BaseTool):
    name: str = "Company Pain Point Analyzer"
    description: str = ( # Updated description to be more generic
        "Analyzes a given company within a specific market segment to infer potential business pain points "
        "or opportunities that align with a client's offerings. Input must be the company name, "
        "segment configuration, and client profile."
    )

    @handle_api_error # Keep for graceful failure of LLM call
    def _run(self, company_name: str, segment_config: dict, client_profile: dict) -> str:
        """
        Uses the configured LLM via LangChain to identify potential pain points
        relevant to the client's offerings for a specific company and segment.
        """
        tool_name = self.name
        segment_name = segment_config.get("SEGMENT_NAME", "Unknown Segment")
        client_name = client_profile.get("CLIENT_NAME", "Our Client")

        logger.info(f"[Tool: {tool_name}] Executing for Company: '{company_name}' (Segment: {segment_name}, Client: {client_name})")

        # --- Input Validation ---
        if not all([
            isinstance(company_name, str) and company_name,
            isinstance(segment_config, dict) and segment_config,
            isinstance(client_profile, dict) and client_profile
        ]):
            error_msg = f"Invalid input provided: company_name='{company_name}', segment_config is_dict='{isinstance(segment_config, dict)}', client_profile is_dict='{isinstance(client_profile, dict)}'"
            logger.error(f"[Tool: {tool_name}] {error_msg}")
            return f"Error: Invalid input provided to PainPointAnalyzerTool. Details: {error_msg}"

        # --- Extract relevant details for the prompt ---
        client_usps_list = client_profile.get("CORE_PRODUCTS_USPS", ["specialized solutions"])
        client_usps_str = "; ".join(client_usps_list)

        segment_pain_examples_list = segment_config.get("SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE", ["their unique challenges"])
        segment_pain_examples_str = "; ".join(segment_pain_examples_list)
        
        segment_product_focus = segment_config.get("PRODUCT_FOCUS_FOR_SEGMENT", "custom solutions")


        # --- Construct the new, specific prompt ---
        # You can add a SystemMessage here too if desired, e.g.,
        # messages = [
        #     SystemMessage(content=f"You are a business analyst for {client_name}, specializing in identifying client needs for custom architectural wood veneer panels."),
        #     HumanMessage(content=prompt_text)
        # ]
        # For simplicity, we'll use a detailed HumanMessage.

        prompt_text = (
            f"**You are a specialized business consultant for {client_name}.**\n"
            f"{client_name} is a premium US-based manufacturer of custom architectural wood veneer panels. "
            f"Key strengths: {client_usps_str}.\n\n"
            f"**Company Profile for Analysis:**\n"
            f"- Name: '{company_name}'\n"
            f"- Segment: '{segment_name}'\n"
            f"- Likely Needs related to Architectural Veneer: {segment_product_focus}. Based on their segment, they often encounter issues such as: {segment_pain_examples_str}.\n\n"
            f"**Your Objective:**\n"
            f"Identify exactly 3 to 5 **highly specific and distinct** business pain points OR unmet needs for '{company_name}' that {client_name} can directly solve with their custom architectural wood veneer panels and associated services. "
            f"Each pain point should clearly imply why '{company_name}' would benefit from partnering with a specialized, high-quality veneer supplier like {client_name}.\n\n"
            f"**CRITICAL GUIDELINES for Pain Points:**\n"
            f"1.  **Specificity is Key:** Focus on practical, operational, project-specific, or quality-control challenges related to specifying, sourcing, or installing wood veneer. "
            f"For example, instead of 'improve quality,' specify 'risk of using non-AWI compliant veneers leading to project rejection.'\n"
            f"2.  **Directly Solvable by {client_name}:** Each point MUST be something {client_name}'s products/services (like AWI Premium Grade, custom capabilities, cut-to-size, reliable delivery) can address.\n"
            f"3.  **Avoid Generic Business Advice:** DO NOT list high-level, generic issues like 'increase profits,' 'reduce costs,' 'improve marketing,' 'find more customers,' or 'manage competition' UNLESS you can tie it *extremely specifically* to a veneer-related problem that {client_name} solves. (e.g., 'High material waste and labor costs due to inaccurately sized veneer panels' is acceptable because cut-to-size services address it).\n"
            f"4.  **Imply a \"Why Now?\" or \"Why Us?\":** The pain should be significant enough to warrant considering a new or specialized supplier like {client_name}.\n" # Note: Escaped quotes around "Why Now?"
            f"5.  **Distinct Points:** Ensure each of the 3-5 points is different and not just a rephrasing of another.\n\n"
            f"**Output Format:**\n"
            f"Provide ONLY a concise, numbered list of these 3-5 pain points/needs. "
            f"NO introductory sentences, NO concluding remarks, NO explanations beyond the points themselves. Start directly with '1.'\n\n"
            f"Example of a good specific pain point (for a Millwork Shop): '1. Difficulty sourcing AWI Premium Grade veneers consistently for high-spec institutional projects, leading to compliance risks or costly rework.'\n"
            f"Example of a bad generic pain point: '1. Needs to improve overall project efficiency.'"
        )

        logger.debug(f"[Tool: {tool_name}] Constructed prompt for '{company_name}':\n{prompt_text}")

        try:
            logger.debug(f"[Tool: {tool_name}] Getting LLM instance from factory...")
            llm = get_llm_instance()
            if llm is None:
                logger.error(f"[Tool: {tool_name}] Failed to get LLM instance.")
                return "Error: LLM instance could not be initialized for pain point analysis."
            logger.debug(f"[Tool: {tool_name}] Using LLM instance type: {type(llm).__name__}")

            logger.debug(f"[Tool: {tool_name}] Making LLM call for '{company_name}'...")
            response = llm.invoke([HumanMessage(content=prompt_text)])
            
            # Extract content (common attribute for LangChain message responses)
            analysis_result = response.content if hasattr(response, 'content') else str(response)

            logger.info(f"[Tool: {tool_name}] LLM call successful for '{company_name}'.")
            logger.debug(f"[Tool: {tool_name}] LLM Response for '{company_name}':\n{analysis_result}")
            
            # Ensure the output is just the list, remove any accidental preamble the LLM might add.
            # A simple way: find the first digit if it's a numbered list.
            match = re.search(r"^\s*\d\.", analysis_result, re.MULTILINE)
            if match:
                analysis_result = analysis_result[match.start():]
            
            return analysis_result.strip()

        except Exception as e:
            logger.error(f"[Tool: {tool_name}] LLM call failed for '{company_name}': {e}", exc_info=True)
            # The @handle_api_error decorator will catch this and return a generic error string,
            # but specific logging here is good.
            return f"Error: LLM query failed during pain point analysis for {company_name}."

# Instantiate the tool (remains the same)
analyze_pain_points_tool = PainPointAnalyzerTool()
