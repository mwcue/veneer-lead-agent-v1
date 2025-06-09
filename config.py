# config.py
import os
from dotenv import load_dotenv
from utils.logging_utils import setup_logging

# Load environment variables
load_dotenv()

class Config:
    """Central configuration for the HR & Regional B2B Lead Generation system."""

    # --- API Keys ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

    # --- LLM Settings ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower() # Default to openai, ensure lowercase

    # Specific model names per provider
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-3.5-turbo")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL","anthropic/claude-3-5-haiku-20241022")     #  "claude-3-sonnet-20240229")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini/gemini-1.5-flash") # Use flash as a reasonable default
    MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral/mistral-large-lates")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ollama/llama3.2")


    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    # --- Agent Settings ---
    RESEARCH_AGENT_MAX_ITER = int(os.getenv("RESEARCH_AGENT_MAX_ITER", "10"))
    ANALYSIS_AGENT_MAX_ITER = int(os.getenv("ANALYSIS_AGENT_MAX_ITER", "10")) # Reviewer uses this too

    # --- URLs Processing ---
    MAX_URLS_TO_PROCESS = int(os.getenv("MAX_URLS_TO_PROCESS", "10")) # Keep at 10 as decided

    # --- Output Settings ---
    OUTPUT_PATH = os.getenv("OUTPUT_PATH", os.path.join(os.path.dirname(__file__), "output.csv"))

    # --- Logging ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # Ensure uppercase for logging levels

    # --- API Rate Limits (Optional - not directly used by factory but good practice) ---
    OPENAI_RATE_LIMIT_RETRY = int(os.getenv("OPENAI_RATE_LIMIT_RETRY", "3"))
    SERPER_RATE_LIMIT_RETRY = int(os.getenv("SERPER_RATE_LIMIT_RETRY", "3"))

    # --- Request Retry Settings (Optional - relevant for scraper/requests) ---
    API_RETRY_DELAY = int(os.getenv("API_RETRY_DELAY", "2"))
    API_RETRY_BACKOFF = int(os.getenv("API_RETRY_BACKOFF", "2"))

    # --- Scraper Settings ---
    SCRAPER_REQUEST_TIMEOUT = int(os.getenv("SCRAPER_REQUEST_TIMEOUT", "20"))

    # --- Company Filtering ---
    GENERIC_COMPANY_NAMES = [
        'company', 'organization', 'the firm', 'client',
        'example', 'test', 'none', 'n/a', 'website', 'url'
    ]

    @classmethod
    def validate(cls):
        """Validate critical configuration settings based on chosen provider."""
        missing_keys = []

        supported_providers_requiring_keys = ["openai", "anthropic", "google", "mistralai"]
        all_supported_providers = supported_providers_requiring_keys + ["ollama"]

        # Always check Serper
        if not cls.SERPER_API_KEY:
            missing_keys.append("SERPER_API_KEY")

        # Check provider-specific key if required
        provider = cls.LLM_PROVIDER # Read the provider set in config (from .env)

        # Check provider-specific key
        if provider == "openai" and not cls.OPENAI_API_KEY:
            missing_keys.append("OPENAI_API_KEY (for selected provider 'openai')")
        elif provider == "anthropic" and not cls.ANTHROPIC_API_KEY:
            missing_keys.append("ANTHROPIC_API_KEY (for selected provider 'anthropic')")
        elif provider == "google" and not cls.GOOGLE_API_KEY:
            missing_keys.append("GOOGLE_API_KEY (for selected provider 'google')")
        elif provider == "mistralai" and not cls.MISTRAL_API_KEY:
            missing_keys.append("MISTRAL_API_KEY (for provider '{provider}')")
        elif provider == "ollama":
            pass # no api key needed for ollama
        elif cls.LLM_PROVIDER not in all_supported_providers:
             missing_keys.append(f"LLM_PROVIDER '{provider}' is not recognized/supported by config validation. Supported: {all_supported_providers}")

        return missing_keys

    @classmethod
    def configure_logging(cls):
        """Configure logging based on settings."""
        # Moved setup_logging import here to avoid potential circular dependency if utils imports config
        from utils.logging_utils import setup_logging
        setup_logging(cls.LOG_LEVEL)


# config.py
# ... (all existing Config class and other code) ...

# --- Client-Specific Campaign Brief ---
# TODO: In the future, this could be loaded from a YAML/JSON file per client.
SJ_MORSE_PROFILE = {
    "CLIENT_NAME": "SJ Morse",
    "WEBSITE": "https://sjmorse.com/",
    "CORE_PRODUCTS_USPS": [
        "Manufacturer of custom architectural wood veneer panels.",
        "AWI Premium Grade certification (signifies high quality and adherence to standards).",
        "Full-service capabilities: veneer selection, engineering, manufacturing, delivery.",
        "Value-added services: cut-to-size, edge-banding, sketch-faces, CNC machining.",
        "Experience with diverse projects: government buildings, corporate offices, hospitality, civic/cultural spaces, high-end residential (e.g., yachts implied).",
        "In-house truck delivery (potential USP for regional clients - mentioned in earlier prompt, good to keep in mind)."
    ],
    "EXISTING_CLIENT_INFO": [
        "~250 clients served over the years.",
        "Approx. 50% are members of the Architectural Woodwork Institute (AWI).",
        "Some clients found via Decorative Hardwoods Association."
    ],
    "TARGET_SEGMENTS": [
        # === EXISTING SEGMENT 1: General Contractors & Design-Build Firms ===
#        {
#            "SEGMENT_NAME": "General Contractors & Design-Build Firms",
#            "SEARCH_KEYWORDS_EXAMPLES": [ 
#                "top general contractors Washington DC", "leading design-build firms Philadelphia",
#                "commercial construction companies NYC", "Richmond VA general contractors",
#                "general contractors specializing in corporate interiors [region]",
#                "design-build firms hospitality projects [region]"
#            ],
#            "GEOGRAPHIC_FOCUS_TEXT": "DC-Baltimore metro, Philadelphia metro, New York City metro, Richmond metro",
#            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["Washington DC", "Baltimore MD", "Philadelphia PA", "New York NY", "Richmond VA"],
#           "PROJECT_CRITERIA_EXAMPLES": [ 
#                "Handling mid-to-large scale commercial or institutional projects.",
#                "Projects involving significant interior finishing work.",
#                "Value quality and adherence to specifications (AWI).",
#                "Likely to subcontract millwork and veneer panel supply."
#            ],
#            "DECISION_MAKER_TITLES_TO_SUGGEST": [ 
#                "Project Executive", "Senior Project Manager", "Purchasing Manager",
#                "Director of Preconstruction", "Estimator"
#            ],
#            "SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE": [ 
#                "Difficulty holding millwork subcontractors accountable to strict AWI Premium Grade veneer specifications, leading to potential rework or client disputes.",
#                "Project delays caused by veneer panel suppliers with long or unreliable lead times, impacting overall construction schedules.",
#                "Receiving veneer panels damaged during long-haul freight, causing costly replacements and project setbacks (mitigated by SJ Morse's regional delivery).",
#                "Challenges in achieving consistent grain, color, and finish for veneer panels across large or phased projects when sourcing from multiple or less capable suppliers.",
#                "Struggles to find a single, reliable veneer panel supplier who can handle complex custom requirements AND provide value-added services like cut-to-size or edge-banding.",
#                "Increased on-site labor costs and material waste due to inaccuracies in veneer panels not supplied as precisely cut-to-size."
#            ],
#            "PRODUCT_FOCUS_FOR_SEGMENT": "High-quality, custom architectural wood veneer panels, potentially with cut-to-size and edge-banding services to support their millwork subs or direct installation."
#        },
        # === EXISTING SEGMENT 2: Architects & Interior Designers ===
        {
            "SEGMENT_NAME": "Architects & Interior Designers (Corporate & Luxury Focus)",
            "SEARCH_KEYWORDS_EXAMPLES": [ 
                "top architectural firms hospitality design [city/state]",
                "interior design firms civic projects [city/state]",
                "A&E firms cultural building design [city/state]",
                "largest architecture companies [city/state] corporate interiors"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Firms with significant portfolios in hospitality, civic, or cultural projects, potentially operating in or specifying for projects in the Mid-Atlantic and surrounding regions.",
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["New York NY", "Philadelphia PA", "Washington DC", "Boston MA", "Chicago IL", "national"],
            "PROJECT_CRITERIA_EXAMPLES": [
                "Mid-to-large A/E firms.",
                "Strong portfolio in hospitality, civic, cultural, or high-end corporate interiors.",
                "Specify materials and often influence contractor/millworker selection.",
                "Value design flexibility, unique veneers, and technical support.",
                "Interested in sustainability and material certifications (like AWI)."
            ],
            "DECISION_MAKER_TITLES_TO_SUGGEST": [
                "Principal Architect", "Senior Architect", "Project Architect",
                "Interior Design Director", "Senior Interior Designer", "Specifications Writer"
            ],
            "SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE": [
                "Inability to source rare, exotic, or highly specific wood veneers required to realize unique and high-impact design concepts.",
                "Concerns that the specified AWI Premium Grade veneer quality and aesthetic intent will be compromised during fabrication or by value-engineering from contractors.",
                "Lack of accessible, expert technical support from veneer suppliers regarding species suitability, matching techniques, finishing options, and AWI standards compliance for complex designs.",
                "Difficulty in confidently specifying and sourcing veneers that meet project sustainability goals (e.g., FSC certified) without compromising on aesthetics or availability.",
                "Limitations in creating intricate sketch-faces, custom inlays, or complex panel sequences due to lack of supplier capability in advanced CNC machining and sequencing.",
                "Challenges in obtaining high-quality physical samples or detailed pre-production visualizations to ensure veneer selections align with client expectations and overall design palette."
            ],
            "PRODUCT_FOCUS_FOR_SEGMENT": "Wide range of custom veneers, sketch-faces, unique species, and technical support for specification. AWI certification is a key selling point."
        },

        # === NEW SEGMENT 3: Architectural Millwork & Woodworking Shops ===
        {
            "SEGMENT_NAME": "Specialty Millwork & Architectural Woodworking Shops",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "custom millwork shops [city/state]", "architectural woodworking companies [region]",
                "AWI certified millwork shops", "commercial casework manufacturers [region]",
                "veneer panel fabrication shops"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Primary: WV, VA, MD, DC, PA, NJ, DE, southern NY. Secondary: Broader East Coast for specialized projects.",
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["West Virginia", "Virginia", "Maryland", "Washington DC", "Pennsylvania", "New Jersey", "Delaware", "New York (southern)"], # Can add more specific cities
            "PROJECT_CRITERIA_EXAMPLES": [
                "Small-to-midsize shops.",
                "Typically handle projects in the $250K - $3M range where veneer is a component.",
                "Directly purchase and fabricate veneer panels.",
                "Value consistent quality, reliable delivery, and technical support from veneer supplier.",
                "May require AWI Premium Grade certification for their projects."
            ],
            "DECISION_MAKER_TITLES_TO_SUGGEST": [
                "Owner", "President", "Shop Manager", "Lead Estimator", "Purchasing Agent", "Senior Project Manager"
            ],
            "SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE": [
                "Inconsistent veneer quality (thickness, grading, finish) from suppliers leading to fabrication issues and material waste.",
                "Unreliable delivery timelines for veneer panels, causing bottlenecks in shop production and project delays.",
                "Difficulty sourcing specific veneers or achieving AWI Premium Grade compliance for demanding client projects.",
                "Need for value-added services like precise cut-to-size or edge-banding to optimize shop workflow and reduce labor.",
                "Limited access to technical expertise from veneer suppliers for challenging applications or new materials.",
                "High cost or unavailability of short runs or highly custom veneer panel orders from larger, less flexible suppliers."
            ],
            "PRODUCT_FOCUS_FOR_SEGMENT": "AWI Premium Grade veneer panels, cut-to-size panels, edge-banded panels, sketch-faces, reliable supply of diverse veneers, technical support for fabrication."
        },

        # === NEW SEGMENT 4: Institutional & Government Owners ===
        {
            "SEGMENT_NAME": "Institutional & End-User Owners (Corporate, Govt, Healthcare, Education)",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "university facilities management [state]", "hospital capital projects [region]",
                "government building renovation contracts", "courthouse construction GSA",
                "public library interior upgrades"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Focus on institutions within SJ Morse's primary service region (WV, VA, MD, DC, PA, NJ, DE, southern NY) due to direct relationship potential and delivery advantages.",
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["Washington DC (federal/local govt)", "Baltimore MD (universities/hospitals)", "Philadelphia PA (healthcare/education)", "Richmond VA (state govt/universities)"], # Example focus areas
            "PROJECT_CRITERIA_EXAMPLES": [
                "Facilities departments, procurement offices.",
                "Often have ongoing renovation/capital improvement programs.",
                "May have annual maintenance or upgrade contracts for interior finishes exceeding $500K where veneer is relevant.",
                "Require durable, high-quality, and often certified materials (AWI, fire ratings).",
                "Procurement processes can be complex; value reliable and compliant suppliers."
            ],
            "DECISION_MAKER_TITLES_TO_SUGGEST": [
                "Director of Facilities", "Capital Projects Manager", "University Architect",
                "Chief Procurement Officer", "Contracting Officer", "Interior Standards Manager"
            ],
            "SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE": [
                "Need for long-term material matching for phased renovations or repairs in existing veneered spaces.",
                "Stringent requirements for material certifications (AWI Premium, fire ratings, sustainability) and supplier compliance.",
                "Challenges finding suppliers who can meet complex government or institutional procurement requirements.",
                "Importance of durability and longevity of veneer panels in high-traffic public or institutional settings.",
                "Desire for single-source, reliable suppliers for large or ongoing veneer needs to simplify project management.",
                "Budget constraints requiring cost-effective yet high-quality and durable veneer solutions."
            ],
            "PRODUCT_FOCUS_FOR_SEGMENT": "Durable AWI Premium Grade veneer panels, fire-rated panels (if offered), long-term matching capabilities, ability to handle large/phased orders, compliance documentation."
        },

        # === NEW SEGMENT 5: High-End Residential & Specialty Outfitters ===
        # (e.g., custom home builders, yacht fitters, luxury retail designers)
        {
            "SEGMENT_NAME": "Luxury Residential, Yacht & Private Aviation Outfitters",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "luxury home builders [city/state]", "custom yacht interior outfitters",
                "high-end residential architects [region]", "bespoke furniture makers wood veneer",
                "luxury retail store designers wood interiors"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Can be national or international for very high-end projects, but initial focus on those accessible within or near SJ Morse's primary service region for ease of collaboration.",
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["New York NY", "South Florida (yachts)", "Los Angeles CA", "major luxury markets", "East Coast luxury home builders"], # Broader, but can be refined
            "PROJECT_CRITERIA_EXAMPLES": [
                "Projects with very high budgets (e.g., residences $5M+, yacht interiors).",
                "Extreme emphasis on unique materials, flawless craftsmanship, and customization.",
                "Often involve intricate designs and exotic or rare veneers.",
                "Clientele expects absolute perfection and highly personalized service."
            ],
            "DECISION_MAKER_TITLES_TO_SUGGEST": [
                "Principal (Custom Builder/Designer)", "Lead Interior Designer (Luxury)", 
                "Project Manager (High-End Residential)", "Owner's Representative", "Purchasing for Yacht Fit-out"
            ],
            "SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE": [
                "Extreme difficulty in sourcing unique, exotic, or perfectly sequence-matched veneer flitches for one-of-a-kind luxury projects.",
                "Intolerance for any imperfections in veneer quality, finish, or panel fabrication; requires master craftsmanship.",
                "Need for highly customized panel sizes, shapes, and intricate details (e.g., complex sketch-faces, inlays) beyond standard capabilities.",
                "Requirement for absolute discretion and white-glove service throughout the specification, production, and delivery process.",
                "Challenges in finding suppliers who understand the aesthetic and technical demands of ultra-luxury interiors (e.g., superyachts, penthouses).",
                "Logistical complexities of delivering delicate, high-value veneer panels to exclusive or hard-to-reach locations."
            ],
            "PRODUCT_FOCUS_FOR_SEGMENT": "Most exotic and highest-grade veneers, flawless book-matching and sequence-matching, complex sketch-faces, CNC precision, custom finishing, exceptional service and project management for veneer components."
        }
    ]
}
