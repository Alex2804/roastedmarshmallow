from .field_encoder import FieldEncoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, visitor

from marshmallow.fields import Nested


class NestedEncoder(FieldEncoder[Nested]):
    def _encode_deserialize(self, nested: Nested, context: CompileContext) -> EncodedReturn:
        with context.stacks.scope(DeserializeArgs(object=f'{context.stacks.object}.schema')):
            return visitor.deserialize(nested.schema, context)

    def _encode_serialize(self, nested: Nested, context: CompileContext) -> EncodedReturn:
        with context.stacks.scope(SerializeArgs(object=f'{context.stacks.object}.schema',
                                                obj=context.stacks.value)):
            return visitor.serialize(nested.schema, context)


visitor.register_encoder(NestedEncoder)
