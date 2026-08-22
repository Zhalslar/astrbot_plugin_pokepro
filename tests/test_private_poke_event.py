from types import SimpleNamespace

from astrbot.api.message_components import Poke

from core.model import PokeEvent


class _Event:
    message_obj = SimpleNamespace(
        raw_message={
            "post_type": "message",
            "message_type": "private",
            "self_id": 100,
            "user_id": 200,
        }
    )

    def __init__(self, components):
        self._components = components

    def get_messages(self):
        return self._components


def test_private_message_poke_component_is_normalized():
    poke = Poke(id="100")
    event = PokeEvent.from_event(_Event([poke]))

    assert event is not None
    assert event.target_id == 100
    assert event.user_id == 200
    assert event.is_private_poke
    assert event.is_self_poked


def test_plain_private_message_is_not_a_poke():
    assert PokeEvent.from_event(_Event([])) is None
