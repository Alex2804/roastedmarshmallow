from .field_encoder import FieldEncoder, CompileContext, EncodedReturn, visitor, Template

from marshmallow.fields import Boolean


_template = '''
try:
    if $value in $truthy:
        $set_result_True
    elif $value in $falsy:
        $set_result_False
    else:
        $handle_not_in_truthy_and_falsy
except TypeError as __error:
    $handle_type_error
'''.strip()


class BooleanEncoder(FieldEncoder[Boolean]):
    @staticmethod
    def _truthy_falsy_id(truthy_falsy: set) -> int:
        return abs(hash(tuple(truthy_falsy)))

    def _encode(self, boolean: Boolean, context: CompileContext, handle_not_in_truthy_and_falsy: str,
                handle_type_error: str) -> EncodedReturn:
        if context.flags.always_inline_bool or (not boolean.truthy and not boolean.falsy):
            return EncodedReturn(code=self.set_result(context, f'bool({context.stacks.value})'))

        truthy_key = f'truthy_{self._truthy_falsy_id(boolean.truthy)}'
        falsy_key = f'falsy_{self._truthy_falsy_id(boolean.falsy)}'

        template = Template(_template)
        template.substitute_indented(handle_not_in_truthy_and_falsy=handle_not_in_truthy_and_falsy,
                                     handle_type_error=handle_type_error)
        template.safe_substitute(value=context.stacks.value,
                                 truthy=truthy_key,
                                 falsy=falsy_key,
                                 set_result_True=self.set_result(context, 'True'),
                                 set_result_False=self.set_result(context, 'False'))

        return EncodedReturn(code=str(template),
                             locals_={truthy_key: (boolean.truthy, str(boolean.truthy)),
                                      falsy_key: (boolean.falsy, str(boolean.falsy))})

    def _encode_deserialize(self, boolean: Boolean, context: CompileContext) -> EncodedReturn:
        raise_invalid_error = f'raise {context.stacks.object}.make_error("invalid", input={context.stacks.value})'
        return self._encode(boolean, context, raise_invalid_error, f'{raise_invalid_error} from __error')

    def _encode_serialize(self, boolean: Boolean, context: CompileContext) -> EncodedReturn:
        set_value = self.set_result(context, f'bool({context.stacks.value})')
        return self._encode(boolean, context, set_value, set_value)


visitor.register_encoder(BooleanEncoder)
