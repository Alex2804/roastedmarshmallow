# Roasted Marshmallow

a Python code generator to improve the de-serialization process of the marshmallow library.

The code generator uses the visitor pattern to traverse marshmallow objects and produce optimized Python code that maps
input data directly to Python objects. By eliminating marshmallow’s reflection-based de-serialization, the code
generator significantly improves performance of de-serialization.

It is possible to add custom code generation for specific marshmallow fields, and the code generator can be extended to
support your own custom marshmallow schema.

It was part of a study project to improve the de-serialization performance in the [Extra-P Project](https://github.com/extra-p/extrap).
You can find the final Report [here](report-roasted-marshmallow.pdf).
