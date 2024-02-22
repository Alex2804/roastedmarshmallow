import inspect
import logging

from .encoder import Encoder, DeserializeArgs, SerializeArgs
from ..utils.compile_context import CompileContext, EncodedReturn

from marshmallow.base import SchemaABC, FieldABC


class _Visitor:
    _type_to_encoder: dict[type[SchemaABC | FieldABC], type[Encoder]] = {}
    _encoders: list[type[Encoder]] = []

    warn_on_fallback_field_encoder = True
    _field_fallback_encoder = None

    warn_on_schema_superclass_encoder = True

    def _find_encoder(self, to_visit: SchemaABC | FieldABC) -> Encoder:
        if type(to_visit) in self._type_to_encoder:
            return self._type_to_encoder[type(to_visit)]()
        elif isinstance(to_visit, FieldABC) and self._field_fallback_encoder is not None:
            if self.warn_on_fallback_field_encoder:
                logging.warning(f"Using fallback encoder for {type(to_visit).__name__}!")
            return self._field_fallback_encoder()
        elif isinstance(to_visit, SchemaABC):
            for e in self._encoders:
                if issubclass(type(to_visit), e.field_type()):
                    if self.warn_on_schema_superclass_encoder:
                        logging.info(f"Using {e.field_type().__name__} superclass encoder for {type(to_visit).__name__}!")
                    return e()
        raise TypeError(f"No encoder for type {type(to_visit).__name__} found!")

    def name(self, to_visit: SchemaABC | FieldABC, attr_name: str) -> str:
        return self._find_encoder(to_visit).encode_name(to_visit, attr_name)

    def deserialize(self, to_visit: SchemaABC | FieldABC, context: CompileContext) -> EncodedReturn:
        return self._find_encoder(to_visit).encode_deserialize(to_visit, context)

    def serialize(self, to_visit: SchemaABC | FieldABC, context: CompileContext) -> EncodedReturn:
        return self._find_encoder(to_visit).encode_serialize(to_visit, context)

    def register_encoder(self, encoder_cls: type[Encoder], override: bool = False):
        if not inspect.isclass(encoder_cls):
            encoder_cls = encoder_cls.__class__

        if not issubclass(encoder_cls, Encoder):
            raise TypeError(f"Expected encoder class, got {type(encoder_cls).__name__} instance!")
        elif not issubclass(encoder_cls.field_type(), (FieldABC, SchemaABC)):
            raise TypeError(f"Expected Encoder for FieldABC or SchemaABC, got {encoder_cls.field_type().__name__}!")
        elif encoder_cls.field_type() in self._encoders and not override:
            raise ValueError(f"Encoder for {encoder_cls.field_type().__name__} already registered!")

        self._type_to_encoder[encoder_cls.field_type()] = encoder_cls
        for i, e in reversed(list(enumerate(self._encoders))):
            if issubclass(e, encoder_cls) or issubclass(e.field_type(), encoder_cls.field_type()):
                self._encoders.insert(i + 1, encoder_cls)
                return
        self._encoders = [encoder_cls] + self._encoders

    def register_field_fallback_encoder(self, encoder_cls: type[Encoder], override: bool = False):
        if not inspect.isclass(encoder_cls):
            encoder_cls = encoder_cls.__class__

        if not issubclass(encoder_cls, Encoder):
            raise TypeError(f"Expected encoder class, got {type(encoder_cls).__name__} instance!")
        elif not issubclass(encoder_cls.field_type(), FieldABC):
            raise TypeError(f"Expected Encoder for FieldABC or SchemaABC, got {encoder_cls.field_type().__name__}!")
        elif self._field_fallback_encoder is not None and not override:
            raise ValueError(f"Field fallback encoder already registered!")
        
        self._field_fallback_encoder = encoder_cls




visitor = _Visitor()
