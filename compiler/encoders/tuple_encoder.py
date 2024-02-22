from .field_encoder import FieldEncoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, visitor


from marshmallow.fields import Tuple


class TupleEncoder(FieldEncoder[Tuple]):
    def _encode_deserialize(self, tpl: Tuple, context: CompileContext) -> EncodedReturn:
        encoded_fields = []
        deserialized = []

        for i, field in enumerate(tpl.tuple_fields):
            with context.stacks.scope(DeserializeArgs(object=f'{context.stacks.object}.tuple_fields[{i}]',
                                                      result=f'deserialized_{context.stacks.scope_counter}_{i}',
                                                      set_result=None,
                                                      value=f'{context.stacks.value}[{i}]',
                                                      data_key=None)):
                encoded_field = visitor.deserialize(field, context)
                encoded_fields.append(encoded_field)
                deserialized.append(context.stacks.result)

        code = '\n\n'.join(encoded_field.code for encoded_field in encoded_fields)
        code += '\n\n' + self.set_result(context, f'({", ".join(deserialized)})')

        return EncodedReturn(code=code, encoded_returns=encoded_fields)

    def _encode_serialize(self, tpl: Tuple, context: CompileContext) -> EncodedReturn:
        encoded_fields = []
        serialized = []
        for i, field in enumerate(tpl.tuple_fields):
            with context.stacks.scope(SerializeArgs(object=f'{context.stacks.object}.tuple_fields[{i}]',
                                                    result=f'serialized_{i}',
                                                    set_result=None,
                                                    value=f'{context.stacks.value}[{i}]')):
                encoded_field = visitor.serialize(field, context)
                encoded_fields.append(encoded_field)
                serialized.append(context.stacks.result)

        code = '\n\n'.join(encoded_field.code for encoded_field in encoded_fields)
        code += '\n\n' + self.set_result(context, f'({", ".join(serialized)})')

        return EncodedReturn(code=code, encoded_returns=encoded_fields)


visitor.register_encoder(TupleEncoder)
