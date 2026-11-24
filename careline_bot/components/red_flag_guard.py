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

from actions.triage import has_red_flag


@DefaultV1Recipe.register([DefaultV1Recipe.ComponentType.INTENT_CLASSIFIER], is_trainable=False)
class RedFlagGuard(GraphComponent):
    """Forces the intent to `emergency` (confidence 1.0) when a red-flag pattern is present."""

    @staticmethod
    def get_default_config() -> Dict[Text, Any]:
        return {"intent": "emergency"}

    def __init__(self, config: Dict[Text, Any]) -> None:
        self._intent = config["intent"]

    @classmethod
    def create(cls, config: Dict[Text, Any], model_storage: ModelStorage, resource: Resource,
               execution_context: ExecutionContext) -> "RedFlagGuard":
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        for message in messages:
            text = message.get("text")
            if not text or text.startswith("/") or not has_red_flag(text):
                continue
            override = {"name": self._intent, "confidence": 1.0}
            ranking = [r for r in (message.get("intent_ranking") or []) if r.get("name") != self._intent]
            message.set("intent", override, add_to_output=True)
            message.set("intent_ranking", [override] + ranking, add_to_output=True)
        return messages
