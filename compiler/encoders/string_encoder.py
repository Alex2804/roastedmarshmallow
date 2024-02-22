from marshmallow.utils import ensure_text_type

from .field_encoder import FieldEncoder, CompileContext, EncodedReturn, visitor, Template

from marshmallow.fields import String


_deserialize_template = '''
__type = type($value)
if __type == str:
    $set_str_result
elif __type == bytes:
    $set_bytes_result
else:
    raise $field.make_error("invalid")
'''.strip()


class StringEncoder(FieldEncoder[String]):
    def _encode_deserialize(self, string: String, context: CompileContext) -> EncodedReturn:
        template = Template(_deserialize_template)
        template.safe_substitute(field=context.stacks.object,
                                 value=context.stacks.value)
        template.substitute_indented(
            set_str_result=self.set_result(context, f'str({context.stacks.value})'),
            set_bytes_result=self.set_result(context, f'str({context.stacks.value}.decode("utf-8"))')
        )
        return EncodedReturn(code=str(template))

    def _encode_serialize(self, string: String, context: CompileContext) -> EncodedReturn:
        value = context.stacks.value
        code = f'str({value}.decode("utf-8") if type({value}) == bytes else {value})'
        return EncodedReturn(code=self.set_result(context, code))


visitor.register_encoder(StringEncoder)
