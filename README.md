# HR & Regional B2B Lead Generation Agent (Model Agnostic)

An automated system using CrewAI for identifying potential conference sponsors from two distinct streams:
1.  **HR Industry Companies:** Businesses globally/nationally focused on HR software, consulting, recruitment, benefits, etc.
2.  **New England Regional B2B Companies:** Businesses headquartered or primarily operating in New England (MA, CT, RI, VT, NH, ME) that offer products/services to other businesses and might benefit from reaching regional HR/business leaders.

The system gathers contact information and analyzes potential business motivations for sponsoring HR-related conferences. It is designed to be **model-agnostic**, allowing easy switching between different LLM providers (like OpenAI, Anthropic, Google Gemini) via configuration.

## Overview

This project uses CrewAI to orchestrate multiple AI agents that work together to generate high-quality leads for conference sponsorship. The system:

1.  **Configures LLM:** Initializes a language model instance based on settings in the `.env` file, using a factory pattern for model agnosticism.
2.  **Searches** the web for relevant sources covering *both* the HR industry *and* New England B2B companies using the configured LLM for agent reasoning.
3.  **Extracts** company names and websites from these diverse sources.
4.  **Classifies** each extracted company as either "HR" or "NE_B2B".
5.  **Analyzes** each company using category-specific agents and the configured LLM to find contact emails and identify potential pain points/opportunities relevant to *sponsoring an HR conference*.
6.  **Reviews** the analysis using category-specific reviewer agents and the configured LLM.
7.  **Outputs** the results, including the lead category, to a structured CSV file.

**Note:** The system includes logic to avoid analyzing the same company website multiple times within a single execution run.

## Prerequisites

-   Python 3.8+
-   Serper API key (`SERPER_API_KEY`)
-   API Key for at least one supported LLM provider (see Model Agnosticism section).

## Installation

1.  Clone this repository:
    ```bash
    git clone https://github.com/yourusername/hr-lead-generation.git # Replace with your repo URL
    cd hr-lead-generation
    ```
2.  Install dependencies (this now includes libraries for multiple LLM providers):
    ```bash
    pip install -r requirements.txt
    ```
3.  Create a `.env` file in the project root and configure it (see Configuration section below).

## Configuration & Model Selection

Configuration is primarily handled via the `.env` file in the project root.

**Key `.env` Variables:**

```dotenv
# --- LLM Provider Selection ---
# Set this to the provider you want to use.
# Supported options (based on utils/llm_factory.py): "openai", "anthropic", "google"
LLM_PROVIDER="openai"

### Important Note on Provider Compatibility (Current Status)

While this project is structured for model agnosticism using the LLM Factory, **current testing (as of the versions used during development) has revealed persistent integration issues when using providers other than OpenAI, particularly when agent tools are involved.**

*   **Errors Encountered:** When setting `LLM_PROVIDER` to `"anthropic"`, `"google"`, or `"ollama"`, errors such as `litellm.BadRequestError: LLM Provider NOT provided...` or `IndexError: list index out of range` (specifically within LiteLLM's Ollama prompt transformation related to `tool_calls`) were frequently encountered during agent execution steps (like the initial Search or Analysis phases).
*   **Root Cause:** These errors appear to stem from incompatibilities in how the provider context and tool usage information are passed between CrewAI, the specific LangChain provider libraries (e.g., `ChatAnthropic`, `ChatOllama`), and the underlying LiteLLM library used by CrewAI. LiteLLM fails to reliably determine the correct provider or process tool-related messages for these non-OpenAI models within this specific execution stack.
*   **Recommendation:** For **full functionality and reliable execution** of all agent tasks (including those requiring tools like web search and analysis), **using the OpenAI provider (`LLM_PROVIDER="openai"`) is currently recommended and known to be stable.**
*   **Experimentation:** You are welcome to experiment with the other configured providers (`anthropic`, `google`, `ollama`, `mistralai`) by changing the `.env` settings. The LLM Factory will correctly initialize them. However, be aware that you may encounter the errors mentioned above until underlying compatibility issues in the `crewai`, `litellm`, or `langchain-*` libraries are resolved in future updates.

We hope future library updates will improve compatibility and make switching providers seamless for all features.


# --- API Keys (Provide key for the selected LLM_PROVIDER above) ---
OPENAI_API_KEY="sk-YourActualOpenAIKeyHere"
ANTHROPIC_API_KEY="sk-ant-YourActualAnthropicKeyHere"
GOOGLE_API_KEY="AIzaYourActualGoogleApiKeyHere"

# --- Model Names (Optional - Defaults exist in config.py) ---
# You can override the default model for the selected provider if needed.
# OPENAI_MODEL="gpt-4o"
# ANTHROPIC_MODEL="claude-3-opus-20240229"
# GEMINI_MODEL="gemini-1.5-pro"

# --- Other Required Config ---
SERPER_API_KEY="YourActualSerperKeyHere"

# --- Core Settings ---
LLM_TEMPERATURE="0.1" # Controls LLM creativity (lower is more deterministic)
MAX_URLS_TO_PROCESS="10" # How many search result URLs to process

# --- Optional Fine-tuning ---
# LOG_LEVEL="DEBUG" # Set to DEBUG for detailed logs, INFO for standard
# RESEARCH_AGENT_MAX_ITER="10"
# ANALYSIS_AGENT_MAX_ITER="10"
# OUTPUT_PATH="output.csv"
# SCRAPER_REQUEST_TIMEOUT="20"
# API_RETRY_DELAY="2"
# API_RETRY_BACKOFF="2"

**To Switch LLM Provider:**

1.  Ensure you have added the necessary API key for the desired provider in your `.env` file.
2.  Change the value of `LLM_PROVIDER` in your `.env` file to the desired supported provider (e.g., change `"openai"` to `"anthropic"` or `"google"`).
3.  (Optional) Change the corresponding model name variable (e.g., `ANTHROPIC_MODEL`) if you don't want to use the default.
4.  Re-run the script (`python main.py`). The system will automatically use the newly configured provider and model via the LLM factory.

## Usage

Run the system with:
```bash python main.py

Results will be saved to output.csv (or the path specified in OUTPUT_PATH). The output file includes leads from both categories, distinguished by the Lead Category column.

## Project Structure

-   `main.py`: Main execution script (includes classification logic)
-   `agents.py`: CrewAI agent definitions (1 Research, 2 Analysis, 2 Reviewer) - uses LLM factory
-   `tasks.py`: Task definitions for CrewAI (updated for dual context)
-   `config.py`: Configuration settings (reads from `.env`)
-   `url_processor.py`: URL search and processing
-   `company_extractor.py`: Company information extraction & analysis routing
-   `output_manager.py`: CSV output generation (includes Lead Category)
-   `tools/`: Custom tools for the agents
    -   `scraper_tools.py`: Web scraping functionality
    -   `unified_email_finder.py`: Email finding tools
    -   `llm_tools.py`: LLM-based analysis tools (pain point generation) - uses LLM factory
    -   `search_tools.py`: Web search functionality (Serper)
    -   `llm_service.py`: **(DELETED)** - No longer used.
-   `utils/`: Utility modules
    -   `llm_factory.py`: **(NEW)** Creates LLM instances based on config.
    -   `logging_utils.py`: Logging setup and error collection
    -   `api_cache.py`: (If used) API response caching
    -   `parser.py`: (If used) Data parsing utilities
    -   `error_handler.py`: Retry decorators and error handling

## Workflow (Dual Stream & Model Agnostic)

1.  **Initialization:** Reads `.env`, sets up logging, initializes the configured LLM via `llm_factory.py`.
2.  **Research Phase (Unified):** The single `Research Agent` uses the configured LLM to generate search queries for *both* HR industry sources *and* New England B2B sources, executes searches, and extracts company names/websites.
3.  **Classification:** `main.py` classifies each extracted company as "HR" or "NE_B2B".
4.  **Analysis & Refinement Phase (Parallel Streams):**
    *   **Intra-Run Duplicate Check:** Skip already processed websites.
    *   **Routing:** Route company to the appropriate analysis/review stream based on classification.
    *   **Initial Analysis & Review:** The category-specific agents (`hr_` or `ne_b2b_`) use the configured LLM (via the factory) to perform analysis and review tasks tailored to their context.
    *   Compile results.
5.  **Output Phase:** Write results to CSV, including `Lead Category`.

## Troubleshooting

-   **LLM Initialization Errors:** Check `utils/llm_factory.py` logs. Ensure `LLM_PROVIDER` in `.env` matches a supported provider ("openai", "anthropic", "google"). Verify the corresponding API key is correctly set in `.env` and valid. Make sure required `langchain-*` packages are installed (`pip install -r requirements.txt`).
-   **API Key Issues**: Double-check keys in `.env` for typos. Ensure the key matches the selected `LLM_PROVIDER`.
-   **Rate Limiting**: LangChain integrations might handle some retries, but check provider documentation if issues persist.
-   **Parsing Errors**: Check `DEBUG` logs for scraping or agent output parsing issues.
-   **Classification Accuracy:** Improve `classify_company` in `main.py` if leads are miscategorized.
-   **Lead Relevance (NE B2B):** Refine prompts/backstories for `ne_b2b_` agents/tasks if the connection to HR conference value is weak.

## Extending the System

-   **Add More LLM Providers:**
    1.  Install the provider's LangChain package (e.g., `pip install langchain-mistralai`).
    2.  Add the package to `requirements.txt`.
    3.  Add configuration variables for the new provider's key/model in `.env` and `config.py`.
    4.  Add an `elif provider == "new_provider":` block in `utils/llm_factory.py` to import and instantiate the correct LangChain chat model class.
    5.  Update the `SUPPORTED_PROVIDERS` dict in the factory and the list in this README.
-   Improve the company classification logic.
-   Add more sophisticated tools.
-   Implement cross-run duplicate checking.
