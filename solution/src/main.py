import json
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATASET_DIR = BASE_DIR / "dataset" / "expanded"

TRIGGERS_DIR = DATASET_DIR / "triggers"
MERCHANTS_DIR = DATASET_DIR / "merchants"
CATEGORIES_DIR = DATASET_DIR / "categories"
TEST_PAIRS_FILE = DATASET_DIR / "test_pairs.json"

OUTPUT_DIR = BASE_DIR / "solution" / "output"
OUTPUT_FILE = OUTPUT_DIR / "messages.json"


# ============================================================
# JSON LOADER
# ============================================================

def load_json(path):
    """Load and return JSON data from a file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# CONTEXT LOADER
# ============================================================

def load_context(test_case):
    """
    Load trigger, merchant and category context
    for one test case.
    """

    trigger_id = test_case["trigger_id"]
    merchant_id = test_case["merchant_id"]

    # Load trigger
    trigger_file = TRIGGERS_DIR / f"{trigger_id}.json"
    trigger = load_json(trigger_file)

    # Load merchant
    merchant_file = MERCHANTS_DIR / f"{merchant_id}.json"
    merchant = load_json(merchant_file)

    # IMPORTANT:
    # Category is determined from the merchant's category_slug.
    category_slug = merchant["category_slug"]

    category_file = CATEGORIES_DIR / f"{category_slug}.json"
    category = load_json(category_file)

    return trigger, merchant, category


# ============================================================
# MESSAGE GENERATOR
# ============================================================

def generate_message(trigger, merchant, category):
    """
    Deterministic message generator using:
    trigger + merchant + category context.
    """

    trigger_kind = trigger.get("kind", "")

    merchant_name = merchant["identity"]["name"]
    category_name = category["display_name"]

    # Trigger payload may contain the useful details
    payload = trigger.get("payload", {})

    # --------------------------------------------------------
    # ACTIVE PLANNING INTENT
    # --------------------------------------------------------

    if trigger_kind == "active_planning_intent":
        intent = (
            payload.get("intent")
            or payload.get("topic")
            or payload.get("plan")
            or "your current business plan"
        )

        return (
            f"{merchant_name}: you have an active planning opportunity "
            f"around {intent}. "
            f"Review your {category_name.lower()} offering and prepare "
            f"relevant content or offers."
        )

    # --------------------------------------------------------
    # APPOINTMENT TOMORROW
    # --------------------------------------------------------

    if trigger_kind == "appointment_tomorrow":
        return (
            f"{merchant_name}: you have a customer appointment scheduled "
            f"for tomorrow. Please review the appointment details and "
            f"ensure the team is prepared."
        )

    # --------------------------------------------------------
    # CATEGORY SEASONAL
    # --------------------------------------------------------

    if trigger_kind == "category_seasonal":
        season = (
            payload.get("season")
            or payload.get("event")
            or payload.get("occasion")
            or "the upcoming seasonal period"
        )

        return (
            f"{merchant_name}: {season} may create additional demand for "
            f"your {category_name.lower()} business. "
            f"Consider preparing relevant offers and listing content."
        )

    # --------------------------------------------------------
    # CDE OPPORTUNITY
    # --------------------------------------------------------

    if trigger_kind == "cde_opportunity":
        return (
            f"{merchant_name}: a professional learning opportunity relevant "
            f"to your {category_name.lower()} business is available. "
            f"Review the opportunity if it matches your interests."
        )

    # --------------------------------------------------------
    # CHRONIC REFILL
    # --------------------------------------------------------

    if trigger_kind == "chronic_refill_due":
        return (
            f"{merchant_name}: a chronic refill reminder is due. "
            f"Please review the customer or refill details and follow "
            f"the appropriate reminder process."
        )

    # --------------------------------------------------------
    # PERFORMANCE DIP
    # --------------------------------------------------------

    if trigger_kind == "perf_dip":

        performance = merchant.get("performance_30d", {})

        views_delta = performance.get("7d_delta_views_pct")
        calls_delta = performance.get("7d_delta_calls_pct")

        return (
            f"{merchant_name}: recent performance shows a potential dip. "
            f"Views changed by {views_delta}% and calls changed by "
            f"{calls_delta}%. "
            f"Consider reviewing listing visibility and recent activity."
        )

    # --------------------------------------------------------
    # PERFORMANCE SPIKE
    # --------------------------------------------------------

    if trigger_kind == "perf_spike":

        performance = merchant.get("performance_30d", {})

        views_delta = performance.get("7d_delta_views_pct")
        calls_delta = performance.get("7d_delta_calls_pct")

        return (
            f"{merchant_name}: recent performance is showing positive "
            f"momentum. Views changed by {views_delta}% and calls changed "
            f"by {calls_delta}%. "
            f"Consider building on the activity driving engagement."
        )

    # --------------------------------------------------------
    # COMPETITOR OPENED
    # --------------------------------------------------------

    if trigger_kind == "competitor_opened":
        return (
            f"{merchant_name}: a new competitor signal has appeared in "
            f"your {category_name.lower()} market. "
            f"Consider reviewing your listing, offers and customer "
            f"engagement."
        )

    # --------------------------------------------------------
    # CUSTOMER LAPSED / WINBACK
    # --------------------------------------------------------

    if trigger_kind in {
        "customer_lapsed_soft",
        "winback"
    }:
        return (
            f"{merchant_name}: a customer re-engagement opportunity has "
            f"been identified. Consider a relevant offer or personalised "
            f"follow-up."
        )

    # --------------------------------------------------------
    # DORMANCY
    # --------------------------------------------------------

    if trigger_kind in {
        "dormancy",
        "dormant"
    }:
        return (
            f"{merchant_name}: recent activity suggests a period of "
            f"dormancy. Consider refreshing your listing, offers and "
            f"customer engagement."
        )

    # --------------------------------------------------------
    # FESTIVAL
    # --------------------------------------------------------

    if trigger_kind in {
        "festival_upcoming",
        "festival_diwali"
    }:
        return (
            f"{merchant_name}: a festival opportunity is approaching. "
            f"Consider preparing your {category_name.lower()} offers "
            f"and listing content."
        )

    # --------------------------------------------------------
    # UNVERIFIED BUSINESS PROFILE
    # --------------------------------------------------------

    if trigger_kind in {
        "unverified_gbp",
        "unverified_gbp_sunrise"
    }:
        return (
            f"{merchant_name}: your business profile requires verification. "
            f"Review the profile status and complete the required "
            f"verification steps."
        )

    # --------------------------------------------------------
    # MILESTONE
    # --------------------------------------------------------

    if trigger_kind in {
        "milestone_reached",
        "milestone"
    }:
        return (
            f"{merchant_name}: you've reached an important business "
            f"milestone. Keep building on the customer activity that "
            f"helped achieve it."
        )

    # --------------------------------------------------------
    # RESEARCH DIGEST
    # --------------------------------------------------------

    if trigger_kind == "research_digest":

        digest = category.get("digest", [])

        if digest:
            first_item = digest[0]

            if isinstance(first_item, dict):
                title = (
                    first_item.get("title")
                    or first_item.get("headline")
                    or first_item.get("topic")
                    or "a new research update"
                )
            else:
                title = str(first_item)
        else:
            title = "a new research update"

        return (
            f"{merchant_name}: a relevant {category_name.lower()} research "
            f"update is available — {title}."
        )

    # --------------------------------------------------------
    # COMPLIANCE
    # --------------------------------------------------------

    if trigger_kind == "compliance":
        return (
            f"{merchant_name}: there is a relevant compliance update for "
            f"your {category_name.lower()} business. "
            f"Please review the applicable requirements and effective dates."
        )

    # --------------------------------------------------------
    # RECALL DUE
    # --------------------------------------------------------

    if trigger_kind == "recall_due":

        due_date = (
            payload.get("due_date")
            or payload.get("service_due")
            or "the scheduled date"
        )

        return (
            f"{merchant_name}: a customer recall is due around "
            f"{due_date}. Please review the available appointment "
            f"options and follow the appropriate reminder process."
        )

    # --------------------------------------------------------
    # IPL / LOCAL EVENT
    # --------------------------------------------------------

    if trigger_kind in {
        "ipl_match_delhi",
        "local_event"
    }:
        return (
            f"{merchant_name}: a local event may create an opportunity "
            f"for your {category_name.lower()} business. "
            f"Consider preparing relevant offers and content."
        )

    # --------------------------------------------------------
    # CURIOUS ASK / INFORMATION REQUEST
    # --------------------------------------------------------

    if trigger_kind == "curious_ask_due":
        return (
            f"{merchant_name}: there is a relevant update or opportunity "
            f"worth reviewing for your {category_name.lower()} business. "
            f"Take a look if it matches your current priorities."
        )

    # --------------------------------------------------------
    # HARD LAPSED CUSTOMER
    # --------------------------------------------------------

    if trigger_kind == "customer_lapsed_hard":
        return (
            f"{merchant_name}: a previously active customer has become "
            f"significantly lapsed. Consider a targeted win-back message "
            f"or relevant re-engagement offer."
        )

    # --------------------------------------------------------
    # DORMANT WITH VERA
    # --------------------------------------------------------

    if trigger_kind == "dormant_with_vera":
        return (
            f"{merchant_name}: your business has shown a period of low "
            f"recent activity. Consider refreshing your listing, offers "
            f"and customer engagement."
        )

    # --------------------------------------------------------
    # GBP UNVERIFIED
    # --------------------------------------------------------

    if trigger_kind == "gbp_unverified":
        return (
            f"{merchant_name}: your business profile appears to be "
            f"unverified. Review the profile status and complete the "
            f"required verification steps."
        )

    # --------------------------------------------------------
    # IPL MATCH TODAY
    # --------------------------------------------------------

    if trigger_kind == "ipl_match_today":
        return (
            f"{merchant_name}: an IPL match is taking place today and "
            f"may create a timely opportunity for your "
            f"{category_name.lower()} business. "
            f"Consider relevant offers or promotional content."
        )

    # --------------------------------------------------------
    # REGULATION CHANGE
    # --------------------------------------------------------

    if trigger_kind == "regulation_change":
        return (
            f"{merchant_name}: a regulatory change relevant to your "
            f"{category_name.lower()} business has been identified. "
            f"Please review the applicable requirements and effective date."
        )
    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return (
        f"{merchant_name}: there is a new update relevant to your "
        f"{category_name.lower()} business."
    )


# ============================================================
# PROCESS TEST CASES
# ============================================================

def process_test_pairs():

    test_cases = load_json(TEST_PAIRS_FILE)["pairs"]

    results = []

    for test_case in test_cases:

        trigger, merchant, category = load_context(test_case)

        message = generate_message(
            trigger,
            merchant,
            category
        )

        result = {
            "test_id": test_case.get("test_id"),
            "trigger_id": test_case["trigger_id"],
            "merchant_id": test_case["merchant_id"],
            "category_slug": merchant["category_slug"],
            "trigger_kind": trigger.get("kind"),
            "message": message
        }

        results.append(result)

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    print("Starting Magicpin AI Challenge flow...")
    print(f"Dataset: {DATASET_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = process_test_pairs()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    print()
    print(f"Processed test cases: {len(results)}")
    print(f"Output written to: {OUTPUT_FILE}")
    print()
    print("Flow completed successfully.")


if __name__ == "__main__":
    main()