from .field_encoder import FieldEncoder, CompileContext, EncodedReturn, visitor

from marshmallow.fields import Float


class FloatEncoder(FieldEncoder[Float]):
    def _encode_deserialize(self, float: Float, context: CompileContext) -> EncodedReturn:
        return EncodedReturn(code=self.set_result(context, f'float({context.stacks.value})'))

    def _encode_serialize(self, _: Float, context: CompileContext) -> EncodedReturn:
        return EncodedReturn(code=self.set_result(context, context.stacks.value))


visitor.register_encoder(FloatEncoder)
