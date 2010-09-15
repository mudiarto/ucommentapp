Next major section
=====================

Using indented text:

    A long paragraph of text.

    * With a bullet point.

        + And another bullet.  NOTE: Those preceeding space elements must be the same as the other elements (i.e. both items must use tabs, or both must use spaces).

	Then some more text that is indented with A TAB THIS TIME.


Block quotes are just:

    Indented paragraphs, with spaces.

        and they may nest.


A section containing mathematics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We first calculate a pooled variance, then a :math:`z`-value, and finally a confidence interval based on this :math:`z`.

.. math::
	s_P^2 &= \frac{(n_A -1) s_A^2 + (n_B-1)s_B^2}{n_A - 1 + n_B - 1}\\
	z &= \frac{(\bar{x}_B - \bar{x}_A) - (\mu_B - \mu_A)}{\sqrt{s_P^2 \left(\frac{1}{n_A} + \frac{1}{n_B}\right)}} \\

	\begin{array}{rcccl}
		(\bar{x}_B - \bar{x}_A) - c_t \times \sqrt{s_P^2 \left(\frac{1}{n_A} + \frac{1}{n_B}\right)} &\leq& \mu_B - \mu_A &\leq & (\bar{x}_B - \bar{x}_A) + c_t  \times \sqrt{s_P^2 \left(\frac{1}{n_A} + \frac{1}{n_B}\right)}
	\end{array}

We consider the effect of changing from condition A to condition B to be a significant effect when this confidence interval does not span zero.





























This section is intentionally left blank.  (was due to moving a test out).
















A section for testing images and figures
=============================================

This a particular figure.

.. figure:: the_figure.png
	:alt:	Some alt text
	:scale: 100%
	:width: 750px
	:align: center

	The figure caption.

And the image directive.

.. image:: some_other_figure.png
	:alt:	Some alt test again.


Substitutions
=============

|RST| is a little annoying to type over and over, especially when writing about |RST| itself.

.. |RST| replace:: reStructuredText


A section for testing notes and admonitions
=============================================

.. sidebar:: What is the response variable?

	Response surface methods consider optimization of a single outcome, or response variable, called :math:`y`.  In many instances we are interested in just a single response, but more often we are interested in the a multi-objective response, i.e. there are trade-offs.  For example we can achieve a higher production rate, but it will be at the expense of greater energy use.

.. note:: With title text

    As part of working out which URL names map to which patterns, the ``reverse()`` function has to import all of your URLconf files and examine the name of each view. This involves importing each view function. If there are any errors whilst importing any of your view functions, it will cause reverse() to raise an error, even if that view function is not the one you are trying to reverse.

.. admonition:: Thou shalt not admonish

	Admonition paragraph goes here.

More paragraph text.

.. hint::

    This is an admonition without a title

Final paragraph for this section.

Some more tables
==========================================================

csvtables

Tabular columns: lines are found by induction at the moment.

Graphviz, graph, digraph

inheritance-diagram

+----------+-----------+-----------+-----------+-----------+
| Product  | Corrosion | resistance| Surface   |roughness  |
+----------+-----------+-----------+-----------+-----------+
|          | Coating A |Coating B  | Coating A | Coating B |
+==========+===========+===========+===========+===========+
| K135     | 0.30      | 0.22      | 30        |   42      |
+----------+-----------+-----------+-----------+-----------+
| K136     | 0.45      | 0.39      | 86        |   31      |
+----------+-----------+-----------+-----------+-----------+
| P271     | 0.22      | 0.24      | 24        |   73      |
+----------+-----------+-----------+-----------+-----------+
| P275     | 0.40      | 0.44      | 74        |   52      |
+----------+-----------+-----------+-----------+-----------+
| S561     | 0.56      | 0.36      | 70        |   75      |
+----------+-----------+-----------+-----------+-----------+
| S567     | 0.76      | 0.51      | 63        |   70      |
+----------+-----------+-----------+-----------+-----------+

