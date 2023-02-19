from collections import namedtuple
from dataclasses import dataclass
from re import search
from typing import Union

from helpers import dict_eval, make_list
from exceptions import invalidToModType
from map_translator import TranslatedMap


def condition_dict(layer_name: str, value: int) -> dict:
    return {"name": layer_name, "type": "variable_if", "value": value}


def event_value(k: namedtuple):
    if dict_value := dict_eval(k.key_code):
        return {k.key_type: dict_value}
    return {k.key_type: k.key_code}


def layer_toggle(layer_name, value):
    return {"set_variable": {"name": layer_name, "value": value}}
# return {"set_variable": condition_dict(layer_name, value)}


def local_mods(mods: dict, direction: str, usr_map) -> dict:
    if not mods:
        return {}
    if direction == "from":
        return {"modifiers": mods}
    if mods.get("optional"):
        invalidToModType(usr_map)
    return {"modifiers": mods.get("mandatory")}


def requires_sublayer(layer_name: str) -> str:
    conditions = {"conditions": []}
    found_layer = search("^/(\\w+)/$", layer_name)
    if not found_layer or found_layer.group(1) == "base":
        return conditions
    layer_condition = condition_dict(f"{found_layer.group(1)}_layer", 1)
    conditions["conditions"].append(layer_condition)
    return conditions


@dataclass
class UserMapping:

    from_keys: str
    maps: Union[str, list]

    def __post_init__(self):
        self.map_interpreter(self.maps)

    def items(self):
        return self.tap, self.hold, self.desc

    def map_interpreter(self, maps):
        maps = make_list(maps)
        [maps.append(None) for i in range(3-len(maps))]
        self.tap, self.hold, self.desc = maps


@dataclass
class KaramlizedKey:

    usr_map: UserMapping
    layer_name: str

    def __post_init__(self):

        self.conditions = requires_sublayer(self.layer_name)
        self.layer_toggle = False

        self.update_desc()
        self.update_from()
        self.update_to()
        self.update_conditions()
        self.update_type()

    def from_keycode_localization(self, from_map: str):
        k_list = self.keystruct_list(from_map, "from")
        simple = len(k_list) == 1
        return k_list.pop() if simple else {"simultaneous": k_list}

    def keystruct_list(self, key_map: str, direction: str):
        translated_key = TranslatedMap(key_map)
        key_list = []

        for k in translated_key.keys:
            layer = self.to_layer_check(k, direction)
            key = layer if layer else event_value(k)
            mod_list = local_mods(k.modifiers, direction, self.usr_map)
            key.update(mod_list)
            key_list.append(key)

        return key_list

    def mapping(self):
        map_attrs = [self.desc, self.conditions,
                     self._from, self._to, self._type]
        return {k: v for d in map_attrs if d for k, v in d.items()}

    def to_keycodes_localization(self, to_map: str, to_key_type: str):
        outputs = self.keystruct_list(to_map, to_key_type) if to_map else None
        return {to_key_type: outputs}

    def to_layer_check(self, key: namedtuple, direction: str):
        if key.key_type != "layer":
            return False
        layer_name = f"{key.key_code}_layer"

        if direction == "to_if_alone":
            # Toggle off needs to be created later by copying this object,
            # changing its on value to off, and adding it to the mapping
            self.layer_toggle = True
            self.conditions["conditions"].append(condition_dict(layer_name, 0))
        else:
            self._to.update(
                {"to_after_key_up": [layer_toggle(layer_name, 0)]}
            )

        return layer_toggle(layer_name, 1)

    def update_conditions(self):
        if not self.conditions.get("conditions"):
            self.conditions = None

    def update_desc(self):
        desc = self.usr_map.desc
        self.desc = {"description": desc} if desc else None

    def update_from(self):
        from_map = self.usr_map.from_keys
        self._from = {"from": self.from_keycode_localization(from_map)}

    def update_to(self):
        self._to = {}

        tap_type = "to"
        if hold := self.usr_map.hold:
            self._to.update(self.to_keycodes_localization(hold, "to"))
            tap_type = "to_if_alone"
        if tap := self.usr_map.tap:
            self._to.update(self.to_keycodes_localization(tap, tap_type))
        if not self._to:
            raise Exception(f"Must map 'to' key for: {self.usr_map.from_keys}")

    def update_type(self):
        # TODO: implement other types (mouse_motion_to_scroll)
        self._type = {"type": "basic"}