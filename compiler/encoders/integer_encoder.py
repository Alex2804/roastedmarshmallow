from .field_encoder import FieldEncoder, CompileContext, EncodedReturn, visitor

from marshmallow.fields import Integer


class IntegerEncoder(FieldEncoder[Integer]):
    def _encode_deserialize(self, integer: Integer, context: CompileContext) -> EncodedReturn:
        return EncodedReturn(code=self.set_result(context, f'int({context.stacks.value})'))

    def _encode_serialize(self, _: Integer, context: CompileContext) -> EncodedReturn:
        return EncodedReturn(code=self.set_result(context, context.stacks.value))


visitor.register_encoder(IntegerEncoder)
