from .field_encoder import FieldEncoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, visitor, Template

from marshmallow.fields import Pluck


class __DummyObject__:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class PluckEncoder(FieldEncoder[Pluck]):  # TODO: optimize
    def _encode_deserialize(self, pluck: Pluck, context: CompileContext) -> EncodedReturn:
        with context.stacks.scope(DeserializeArgs(
                object=f'{context.stacks.object}.schema',
                value=f'{"{"}"{pluck._field_data_key}": {context.stacks.value}{"}"}'
        )):
            return visitor.deserialize(pluck.schema, context)

    def _encode_serialize(self, pluck: Pluck, context: CompileContext) -> EncodedReturn:
        set_result = Template(self.set_result(context, '$value'))
        with context.stacks.scope(SerializeArgs(
                object=f'{context.stacks.object}.schema',
                obj=context.stacks.value,
                set_result=lambda v: set_result.safe_substitute(value=f'{v}["{pluck._field_data_key}"]')
        )):
            encoded = visitor.serialize(pluck.schema, context)
            encoded.locals['__DummyObject__'] = (__DummyObject__, f'from {__DummyObject__.__module__} import {__DummyObject__.__name__}')
            return encoded


visitor.register_encoder(PluckEncoder)
