from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TypeVar, Generic, Callable

from marshmallow.base import SchemaABC, FieldABC

from ..utils.compile_context import CompileContext, EncodedReturn


def _check_encoder_type(func):
    def _decorator(self, field, context, *args, **kwargs):
        if issubclass(type(field), self.field_type()):
            return func(self, field, context, *args, **kwargs)
        raise TypeError(f"Expected {self.field_type().__name__}, got {type(field).__name__}")
    return _decorator


_T = TypeVar('_T', SchemaABC, FieldABC)


class Encoder(ABC, Generic[_T]):
    @classmethod
    def field_type(cls) -> type[_T]:
        return cls.__orig_bases__[0].__args__[0]

    @_check_encoder_type
    def encode_name(self, to_encode: _T, attr_name: str) -> str:
        return self._encode_name(to_encode, attr_name)

    def _encode_name(self, to_encode: _T, attr_name: str) -> str:
        return attr_name

    @staticmethod
    def set_result(context: CompileContext, result: str) -> str:
        if context.stacks.get('set_result'):
            return context.stacks.set_result(result)
        return f'{context.stacks.result} = {result}'

    @_check_encoder_type
    def encode_deserialize(self, to_encode: _T, context: CompileContext) -> EncodedReturn:
        return self._encode_deserialize(to_encode, context)

    @abstractmethod
    def _encode_deserialize(self, to_encode: _T, context: CompileContext) -> EncodedReturn:
        ...

    @_check_encoder_type
    def encode_serialize(self, to_encode: _T, context: CompileContext) -> EncodedReturn:
        return self._encode_serialize(to_encode, context)

    @abstractmethod
    def _encode_serialize(self, to_encode: _T, context: CompileContext) -> EncodedReturn:
        ...


class DeserializeArgs(dict):
    def __init__(self,
                 object: str = ...,
                 result: str = ...,
                 set_result: Callable[[str], str] | None = ...,
                 value: str = ...,
                 data: str = ...,
                 data_key: str | None = ...,
                 partial: str = ...,
                 unknown: str = ...):
        super().__init__()
        if object is not ...:
            self['object'] = object
        if result is not ...:
            self['result'] = result
        if set_result is not ...:
            self['set_result'] = set_result
        if value is not ...:
            self['value'] = value
        if data is not ...:
            self['data'] = data
        if data_key is not ...:
            self['data_key'] = data_key
        if partial is not ...:
            self['partial'] = partial
        if unknown is not ...:
            self['unknown'] = unknown


class SerializeArgs(dict):
    def __init__(self,
                 object: str = ...,
                 result: str = ...,
                 set_result: Callable[[str], str] | None = ...,
                 value: str = ...,
                 obj: str = ...,
                 obj_key: str | None = ...):
        super().__init__()
        if object is not ...:
            self['object'] = object
        if result is not ...:
            self['result'] = result
        if set_result is not ...:
            self['set_result'] = set_result
        if value is not ...:
            self['value'] = value
        if obj is not ...:
            self['obj'] = obj
        if obj_key is not ...:
            self['obj_key'] = obj_key
