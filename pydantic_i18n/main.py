import json
import re
from string import Formatter
from typing import TYPE_CHECKING
from typing import Callable
from typing import Dict
from typing import List
from typing import Sequence
from typing import Union

from .loaders import BaseLoader
from .loaders import DictLoader
from .types import BabelRegex

if TYPE_CHECKING:  # pragma: no cover
    from pydantic.error_wrappers import ErrorDict

__all__ = ("PydanticI18n",)


class PydanticI18n:
    def __init__(
        self,
        source: Union[Dict[str, Dict[str, str]], BaseLoader],
        default_locale: str = "en_US",
    ):
        if isinstance(source, dict):
            source = DictLoader(source)

        self.source = source
        self.default_locale = default_locale
        self._patterns = BabelRegex(self.source.get_translations(self.default_locale))

    def _translate(self, message: str, locale: str) -> str:
        source_msg_pattern = self._patterns.get(message)
        if source_msg_pattern:
            target_msg_pattern = self.source.gettext(source_msg_pattern, locale=locale)
            expression = self._patterns.expression(source_msg_pattern)
            expression_compiled = re.compile(expression)
            match = re.match(pattern=expression_compiled, string=message)
            if match:
                groups = match.groups()
                return Formatter().format(target_msg_pattern, *groups)
            return target_msg_pattern
        return message

    @property
    def locales(self) -> Sequence[str]:
        return self.source.locales

    def translate(
        self,
        errors: List["ErrorDict"],
        locale: str,
    ) -> List["ErrorDict"]:
        return [
            {
                **error,  # type: ignore
                "msg": self._translate(error["msg"], locale),
            }
            for error in errors
        ]

    @classmethod
    def get_pydantic_messages(cls, output: str = "dict") -> Union[Dict[str, str], str]:
        output_mapping: Dict[str, Callable[[], Union[Dict[str, str], str]]] = {
            "json": cls._get_pydantic_messages_json,
            "dict": cls._get_pydantic_messages_dict,
            "babel": cls._get_pydantic_messages_babel,
        }

        return output_mapping[output]()

    @classmethod
    def _get_pydantic_messages_dict(cls) -> Dict[str, str]:
        from pydantic import errors

        messages = (
            re.sub(r"\{.+\}", "{}", getattr(errors, name).msg_template)
            for name in errors.__all__
            if hasattr(getattr(errors, name), "msg_template")
        )
        return {value: value for value in messages}

    @classmethod
    def _get_pydantic_messages_json(cls) -> str:
        return json.dumps(cls._get_pydantic_messages_dict(), indent=4)

    @classmethod
    def _get_pydantic_messages_babel(cls) -> str:
        return "\n\n".join(
            f'msgid "{item}"\nmsgstr "{item}"'
            for item in cls._get_pydantic_messages_dict()
        )
