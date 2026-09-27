import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT_DIR / "dataset" / "expanded"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import generate_message


# ------------------------------------------------------------
# GLOBAL STATE
# ------------------------------------------------------------

START_TIME = time.time()

contexts = {
    "category": {},
    "merchant": {},
    "customer": {},
    "trigger": {}
}

context_versions = {
    "category": {},
    "merchant": {},
    "customer": {},
    "trigger": {}
}
def preload_contexts():
    for scope, folder, key in [
        ("category", "categories", "slug"),
        ("merchant", "merchants", "merchant_id"),
        ("customer", "customers", "customer_id"),
        ("trigger", "triggers", "id"),
    ]:
        directory = DATASET_DIR / folder
        if not directory.exists():
            continue

        for path in directory.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                context_id = data.get(key)
                if context_id:
                    contexts[scope][context_id] = data
                    context_versions[scope][context_id] = 1
            except Exception as e:
                print(f"Warning: failed to load {path}: {e}")

    print("Preloaded contexts:", {
        scope: len(values) for scope, values in contexts.items()
    })
conversations = {}

metadata = {
    "team_name": "Magicpin AI Challenge",
    "team_members": ["Harshita Arora"],
    "model": "deterministic-rule-composer",
    "approach": "stateful deterministic context router with trigger-specific composition",
    "contact_email": "team@example.com",
    "version": "1.0.0",
    "submitted_at": datetime.utcnow().isoformat() + "Z"
}


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))

    if length <= 0:
        return {}

    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def normalize_kind(kind):
    """
    Normalize trigger naming differences found in the dataset.
    """

    aliases = {
        "performance_dip": "perf_dip",
        "performance_spike": "perf_spike",
        "renewal": "renewal_due",
        "customer_lapsed": "customer_lapsed_soft",
        "gbp_unverified": "gbp_unverified",
        "unverified_gbp": "gbp_unverified",
        "ipl_match_today": "ipl_match_today",
        "festival_diwali": "festival_diwali",
        "dormant_with_vera": "dormant_with_vera",
        "regulation_change": "regulation_change",
        "curious_ask_due": "curious_ask_due",
        "customer_lapsed_hard": "customer_lapsed_hard",
        "chronic_refill_due": "chronic_refill_due",
    }

    return aliases.get(kind, kind)


def find_context(scope, context_id):
    return contexts.get(scope, {}).get(context_id)


def get_merchant(merchant_id):
    return find_context("merchant", merchant_id)


def get_customer(customer_id):
    if not customer_id:
        return None

    return find_context("customer", customer_id)


def get_category(merchant):
    if not merchant:
        return None

    category_slug = merchant.get("category_slug")

    if not category_slug:
        return None

    return find_context("category", category_slug)


def get_trigger(trigger_id):
    return find_context("trigger", trigger_id)


def merchant_name(merchant):
    identity = merchant.get("identity", {}) if merchant else {}

    return (
        identity.get("name")
        or merchant.get("name")
        or merchant.get("merchant_name")
        or "Merchant"
    )


def customer_name(customer):
    identity = customer.get("identity", {}) if customer else {}

    return (
        identity.get("name")
        or customer.get("name")
        or customer.get("customer_name")
        or "Customer"
    )


def choose_cta(trigger):
    """
    One primary CTA only.
    """

    kind = normalize_kind(trigger.get("kind", ""))

    informational = {
        "research_digest",
        "cde_opportunity",
        "curious_ask_due",
        "milestone_reached",
        "milestone",
        "perf_spike",
        "performance_spike",
        "ipl_match_today",
        "local_event",
        "category_seasonal"
    }

    if kind in informational:
        return "open_ended"

    return "binary_confirm_cancel"


def choose_send_as(trigger):
    return "vera"

def choose_template(trigger):
    kind = normalize_kind(trigger.get("kind", ""))

    templates = {
        "research_digest": "vera_research_digest_v1",
        "recall_due": "vera_recall_v1",
        "perf_dip": "vera_performance_dip_v1",
        "perf_spike": "vera_performance_spike_v1",
        "compliance": "vera_compliance_v1",
        "regulation_change": "vera_compliance_v1",
        "festival_upcoming": "vera_festival_v1",
        "festival_diwali": "vera_festival_v1",
        "competitor_opened": "vera_competitor_v1",
        "milestone_reached": "vera_milestone_v1",
        "milestone": "vera_milestone_v1",
        "gbp_unverified": "vera_gbp_v1",
        "unverified_gbp": "vera_gbp_v1",
        "customer_lapsed_soft": "vera_winback_v1",
        "customer_lapsed_hard": "vera_winback_v1",
        "winback": "vera_winback_v1",
        "dormancy": "vera_dormancy_v1",
        "dormant": "vera_dormancy_v1",
        "dormant_with_vera": "vera_dormancy_v1",
        "appointment_tomorrow": "vera_appointment_v1",
        "chronic_refill_due": "vera_refill_v1",
    }

    return templates.get(kind, "vera_update_v1")


def compose_action(trigger, merchant, category, customer=None):
    """
    Build a complete proactive /tick action.
    """

    kind = normalize_kind(trigger.get("kind", ""))

    # Generate using the existing deterministic composer.
    body = generate_message(
        trigger,
        merchant,
        category
    )

    # Customer-facing message refinement.
    if customer and trigger.get("scope") == "customer":
        name = customer_name(customer)

        if kind == "recall_due":
            payload = trigger.get("payload", {})

            due_date = (
                payload.get("due_date")
                or payload.get("service_due")
                or "the scheduled date"
            )

            body = (
                f"Hi {name}, your next dental recall is due around "
                f"{due_date}. We have appointment options available; "
                f"reply YES if you'd like us to help schedule one."
            )

    action = {
        "conversation_id": "conv_" + uuid.uuid4().hex[:12],
        "merchant_id": trigger.get("merchant_id")
        or merchant.get("merchant_id"),
        "customer_id": trigger.get("customer_id")
        if trigger.get("scope") == "customer"
        else None,
        "send_as": choose_send_as(trigger),
        "trigger_id": trigger.get("id"),
        "template_name": choose_template(trigger),
        "template_params": [
            merchant_name(merchant)
        ],
        "body": body,
        "cta": choose_cta(trigger),
        "suppression_key": trigger.get("suppression_key", ""),
        "rationale": (
            f"Trigger '{kind}' matched to the merchant's "
            f"category and current context; message uses available "
            f"merchant-specific information without inventing data."
        )
    }

    # Save conversation state.
    conversations[action["conversation_id"]] = {
        "conversation_id": action["conversation_id"],
        "merchant_id": action["merchant_id"],
        "customer_id": action["customer_id"],
        "trigger_id": action["trigger_id"],
        "trigger": trigger,
        "merchant": merchant,
        "category": category,
        "customer": customer,
        "sent_bodies": [body],
        "incoming_messages": [],
        "turns": 1,
        "last_action": "send",
        "qualification_turns": 0,
        "auto_reply_count": 0
    }

    return action


# ------------------------------------------------------------
# REPLY HANDLER
# ------------------------------------------------------------

def handle_reply(data):
    conversation_id = data.get("conversation_id")

    if not conversation_id:
        return {
            "action": "end",
            "rationale": "Missing conversation_id; cannot safely continue state."
        }

    state = conversations.get(conversation_id)

    if not state:
        return {
            "action": "end",
            "rationale": "Conversation state not found; ending safely rather than fabricating context."
        }

    message = (data.get("message") or "").strip()

    if not message:
        return {
            "action": "wait",
            "wait_seconds": 900,
            "rationale": "Empty reply received; waiting before another attempt."
        }

    previous_messages = state["incoming_messages"]

    # --------------------------------------------------------
    # REPEATED AUTO-REPLY DETECTION
    # --------------------------------------------------------

    if previous_messages and message.lower() == previous_messages[-1].lower():
        state["auto_reply_count"] += 1
    else:
        state["auto_reply_count"] = 0

    previous_messages.append(message)

    if state["auto_reply_count"] >= 2:
        return {
            "action": "end",
            "rationale": (
                "Auto-reply repeated 3x in a row with no real engagement; "
                "closing the conversation."
            )
        }

    if state["auto_reply_count"] == 1:
        return {
            "action": "wait",
            "wait_seconds": 86400,
            "rationale": (
                "Same auto-reply received twice in a row; "
                "waiting 24h before retry."
            )
        }

    # --------------------------------------------------------
    # HARD NEGATIVE / OPT OUT
    # --------------------------------------------------------

    lower = message.lower()

    negative_phrases = [
        "not interested",
        "no thanks",
        "no thank you",
        "stop",
        "don't contact",
        "do not contact",
        "remove me",
        "leave me alone",
        "not required",
        "not needed"
    ]

    if any(phrase in lower for phrase in negative_phrases):
        return {
            "action": "end",
            "rationale": (
                "Merchant explicitly declined or requested no further "
                "outreach; ending respectfully."
            )
        }

    # --------------------------------------------------------
    # EXPLICIT ACTION / COMMITMENT
    # --------------------------------------------------------

    commitment_phrases = [
        "let's do it",
        "lets do it",
        "yes",
        "go ahead",
        "proceed",
        "do it",
        "sounds good",
        "okay do it",
        "ok do it",
        "confirm",
        "send it",
        "send now"
    ]

    if any(phrase in lower for phrase in commitment_phrases):

        merchant = state["merchant"]
        customer = state.get("customer")
        trigger = state["trigger"]

        if customer:
            body = (
                f"Great — I'll proceed with the next step for "
                f"{customer_name(customer)} based on the available "
                f"customer context."
            )
        else:
            body = (
                f"Great. I'll proceed with the next step for "
                f"{merchant_name(merchant)} based on the current "
                f"trigger and merchant context."
            )

        if body in state["sent_bodies"]:
            body += " I'll keep this step focused on the current request."

        state["sent_bodies"].append(body)
        state["turns"] += 1
        state["last_action"] = "send"

        return {
            "action": "send",
            "body": body,
            "cta": "open_ended",
            "rationale": (
                "Merchant explicitly committed; switching immediately "
                "from qualification to action execution."
            )
        }

    # --------------------------------------------------------
    # TIME / DELAY REQUEST
    # --------------------------------------------------------

    delay_phrases = [
        "later",
        "tomorrow",
        "give me some time",
        "let me think",
        "busy right now",
        "call later",
        "message later"
    ]

    if any(phrase in lower for phrase in delay_phrases):
        return {
            "action": "wait",
            "wait_seconds": 1800,
            "rationale": (
                "Merchant requested more time; backing off for 30 minutes."
            )
        }

    # --------------------------------------------------------
    # OFF-TOPIC REQUEST
    # --------------------------------------------------------

    gst_terms = [
        "gst",
        "tax filing",
        "income tax",
        "tax return"
    ]

    if any(term in lower for term in gst_terms):
        return {
            "action": "send",
            "body": (
                "I can keep this conversation focused on the current "
                "Magicpin business task. For the GST question, please "
                "use your usual tax/accounting support."
            ),
            "cta": "none",
            "rationale": (
                "Off-topic request detected; politely keeping the "
                "conversation on mission."
            )
        }

    # --------------------------------------------------------
    # GENERAL QUALIFICATION
    # --------------------------------------------------------

    state["qualification_turns"] += 1
    state["turns"] += 1

    trigger = state["trigger"]
    merchant = state["merchant"]
    category = state["category"]

    kind = normalize_kind(trigger.get("kind", ""))

    if kind == "perf_dip":
        body = (
            f"Understood. For the current performance dip, the next useful "
            f"step is to review the listing activity and recent visibility "
            f"signals already available for {merchant_name(merchant)}. "
            f"Would you like to proceed with that review?"
        )
    elif kind == "research_digest":
        body = (
            f"Understood. I can keep the discussion focused on the "
            f"research item relevant to {merchant_name(merchant)}. "
            f"Would you like me to proceed with the next step?"
        )
    else:
        body = (
            f"Understood. I can keep this focused on the current "
            f"{kind.replace('_', ' ')} trigger for "
            f"{merchant_name(merchant)}. Would you like to proceed?"
        )

    # Anti-repetition.
    if body in state["sent_bodies"]:
        body = (
            "Understood. I can take the next step using the context "
            "already provided. Shall I proceed?"
        )

    state["sent_bodies"].append(body)
    state["last_action"] = "send"

    return {
        "action": "send",
        "body": body,
        "cta": "binary_confirm_cancel",
        "rationale": (
            "Acknowledging the merchant response while moving the "
            "conversation toward the next concrete step."
        )
    }


# ------------------------------------------------------------
# HTTP HANDLER
# ------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print("[HTTP]", format % args)

    def do_GET(self):

        if self.path == "/v1/healthz":

            counts = {
                scope: len(values)
                for scope, values in contexts.items()
            }

            json_response(
                self,
                200,
                {
                    "status": "ok",
                    "uptime_seconds": int(time.time() - START_TIME),
                    "contexts_loaded": counts
                }
            )
            return

        if self.path == "/v1/metadata":

            json_response(
                self,
                200,
                metadata
            )
            return

        json_response(
            self,
            404,
            {"error": "not_found"}
        )

    def do_POST(self):

        try:
            data = read_json(self)

        except Exception as exc:
            json_response(
                self,
                400,
                {
                    "error": "invalid_json",
                    "detail": str(exc)
                }
            )
            return

        # ----------------------------------------------------
        # CONTEXT
        # ----------------------------------------------------

        if self.path == "/v1/context":

            scope = data.get("scope")
            context_id = data.get("context_id")
            version = data.get("version")
            payload = data.get("payload")

            if scope not in contexts:
                json_response(
                    self,
                    400,
                    {"error": "invalid_scope"}
                )
                return

            if not context_id or version is None or payload is None:
                json_response(
                    self,
                    400,
                    {"error": "missing_required_context_fields"}
                )
                return

            previous_version = context_versions[scope].get(context_id)

            # Idempotent duplicate.
            if previous_version is not None and version == previous_version:
                json_response(
                    self,
                    200,
                    {
                        "accepted": True,
                        "ack_id": "ack_" + uuid.uuid4().hex[:12],
                        "stored_at": datetime.utcnow().isoformat() + "Z"
                    }
                )
                return

            # Reject lower versions.
            if previous_version is not None and version < previous_version:
                json_response(
                    self,
                    409,
                    {
                        "error": "version_conflict",
                        "current_version": previous_version
                    }
                )
                return

            # New/higher version replaces old version.
            contexts[scope][context_id] = payload
            context_versions[scope][context_id] = version

            json_response(
                self,
                200,
                {
                    "accepted": True,
                    "ack_id": "ack_" + uuid.uuid4().hex[:12],
                    "stored_at": datetime.utcnow().isoformat() + "Z"
                }
            )
            return

        # ----------------------------------------------------
        # TICK
        # ----------------------------------------------------

        if self.path == "/v1/tick":

            available = data.get("available_triggers", [])

            actions = []

            for trigger_id in available:

                trigger = get_trigger(trigger_id)

                if not trigger:
                    continue

                merchant_id = trigger.get("merchant_id")
                merchant = get_merchant(merchant_id)

                if not merchant:
                    continue

                category = get_category(merchant)

                if not category:
                    continue

                customer = get_customer(
                    trigger.get("customer_id")
                )

                action = compose_action(
                    trigger,
                    merchant,
                    category,
                    customer
                )

                actions.append(action)

            json_response(
                self,
                200,
                {
                    "actions": actions
                }
            )
            return

        # ----------------------------------------------------
        # REPLY
        # ----------------------------------------------------

        if self.path == "/v1/reply":

            result = handle_reply(data)

            json_response(
                self,
                200,
                result
            )
            return

        json_response(
            self,
            404,
            {"error": "not_found"}
        )


# ------------------------------------------------------------
# SERVER
# ------------------------------------------------------------

def main():
    preload_contexts()

    port = int(__import__("os").environ.get("PORT", "8080"))

    print("=" * 60)
    print("Magicpin AI Challenge Bot")
    print("=" * 60)
    print(f"Root directory: {ROOT_DIR}")
    print(f"Dataset: {DATASET_DIR}")
    print(f"Server: http://localhost:{port}")
    print()
    print("Endpoints:")
    print("  GET  /v1/healthz")
    print("  GET  /v1/metadata")
    print("  POST /v1/context")
    print("  POST /v1/tick")
    print("  POST /v1/reply")
    print()
    print("Press CTRL+C to stop.")
    print("=" * 60)

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
