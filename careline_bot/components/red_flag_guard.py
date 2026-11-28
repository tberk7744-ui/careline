"""Deterministic safety layer on top of the learned intent classifier.

DIET is a statistical model: with limited training data it will sometimes read an emergency statement
as an ordinary symptom report or a booking request. In a triage assistant that error is unacceptable,
so this component runs last in the NLU pipeline and overrides the predicted intent with `emergency`
whenever the patient's text matches a red-flag pattern. Under-triage is prevented by rules; the price is
some over-triage (e.g. "no chest pain" also matches), which is the safe direction to fail in.
"""
from typing import Any, Dict, List, Text

from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message

from actions.triage import asks_about_urgency, has_red_flag


@DefaultV1Recipe.register([DefaultV1Recipe.ComponentType.INTENT_CLASSIFIER], is_trainable=False)
class RedFlagGuard(GraphComponent):
    """Forces `emergency` on a red-flag pattern; maps explicit urgency questions to the `seek_care` safety net."""

    @staticmethod
    def get_default_config() -> Dict[Text, Any]:
        return {"intent": "emergency", "safety_net_intent": "seek_care",
                "keep_intents": ["emergency", "request_human"]}

    def __init__(self, config: Dict[Text, Any]) -> None:
        self._intent = config["intent"]
        self._safety = config["safety_net_intent"]
        self._keep = set(config["keep_intents"])

    @classmethod
    def create(cls, config: Dict[Text, Any], model_storage: ModelStorage, resource: Resource,
               execution_context: ExecutionContext) -> "RedFlagGuard":
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        for message in messages:
            text = message.get("text")
            if not text or text.startswith("/"):
                continue
            if has_red_flag(text):
                target = self._intent
            elif asks_about_urgency(text) and (message.get("intent") or {}).get("name") not in self._keep:
                target = self._safety   # safety net: "should I go to hospital?" -> 112/999 advice + nurse
            else:
                continue
            override = {"name": target, "confidence": 1.0}
            ranking = [r for r in (message.get("intent_ranking") or []) if r.get("name") != target]
            message.set("intent", override, add_to_output=True)
            message.set("intent_ranking", [override] + ranking, add_to_output=True)
        return messages
