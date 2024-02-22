from .field_encoder import FieldEncoder, CompileContext, EncodedReturn, visitor, Template

from marshmallow.fields import Number


_deserialize_template = '''
$validation_template
$set_result
'''.strip()

_deserialize_validation_template = '''
if $value is True or $value is False:
    raise $field.make_error("invalid", input=$value)
'''.strip()


class NumberEncoder(FieldEncoder[Number]):
    @staticmethod
    def _num_type_key(number: Number) -> str:
        return f'{number.num_type.__name__}_{abs(hash(number.num_type))}'

    def _encode_deserialize(self, number: Number, context: CompileContext) -> EncodedReturn:
        num_type_key = self._num_type_key(number)
        
        template = Template(_deserialize_template)
        template.substitute_indented(
            validation_template=_deserialize_validation_template if context.flags.validate else '',
            set_result=self.set_result(context, f'{num_type_key}({context.stacks.value})')
        )
        template.safe_substitute(field=context.stacks.object,
                                 value=context.stacks.value)
        
        return EncodedReturn(code=str(template),
                             locals_={num_type_key: (number.num_type, number.num_type.__name__)})

    def _encode_serialize(self, number: Number, context: CompileContext) -> EncodedReturn:
        num_type_key = self._num_type_key(number)
        code = f'{num_type_key}({context.stacks.value})'
        return EncodedReturn(code=self.set_result(context, f'str({code})' if number.as_string else code),
                             locals_={num_type_key: (number.num_type, number.num_type.__name__)})


visitor.register_encoder(NumberEncoder)
