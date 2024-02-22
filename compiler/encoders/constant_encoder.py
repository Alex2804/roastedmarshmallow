from typing import Hashable

from .field_encoder import FieldEncoder, CompileContext, EncodedReturn, visitor

from marshmallow.fields import Constant


class ConstantEncoder(FieldEncoder[Constant]):
    @staticmethod
    def __constant_key(constant: Constant) -> str:
        constant_id = abs(hash(constant.constant)) if isinstance(constant.constant, Hashable) else id(constant.constant)
        return f'{constant.__class__.__name__}_{constant_id}'

    def _encode(self, constant: Constant, context: CompileContext) -> EncodedReturn:
        constant_key = self.__constant_key(constant)
        return EncodedReturn(code=self.set_result(context, constant_key),
                             locals_={constant_key: (constant.constant, f'{context.stacks.object}.constant')})

    def _encode_deserialize(self, constant: Constant, context: CompileContext) -> EncodedReturn:
        return self._encode(constant, context)

    def _encode_serialize(self, constant: Constant, context: CompileContext) -> EncodedReturn:
        return self._encode(constant, context)


visitor.register_encoder(ConstantEncoder)
