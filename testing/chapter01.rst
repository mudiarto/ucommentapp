##################
The first chapter
##################

.. Testing newlines within a paragraph.

Developed four years ago by a fast-moving online-news operation, Django was
designed to handle two challenges: the intensive deadlines of a newsroom and
the stringent requirements of the experienced Web developers who wrote it. 
It lets you build high-performing, elegant Web applications quickly.

The first section
=================

.. Testing one long line for the paragraph.

The goal of this document is to give you enough technical specifics to understand how Django works, but this isn’t intended to be a tutorial or reference – but we’ve got both! When you’re ready to start a project, you can start with the :ref:`tutorial <tutorial-section>` or dive right into more detailed documentation.

.. _`tutorial-section`:

Tutorial
========

.. Testing some basic formatting.

In this page we will write a simple *view function*.  These Python functions exist in a file called ``views.py``, a file inside your Django **application**.

References and hyperlinks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See the `Python home page <http://www.python.org>`_ for info.

This is exactly equivalent to:

See the `Python home page`_ for info.

.. _Python home page: http://www.python.org

Anonymous hyperlinks example:

`RFC 2396`__ and `RFC 2732`__ together define the syntax of URIs.

__ http://www.rfc-editor.org/rfc/rfc2396.txt
__ http://www.rfc-editor.org/rfc/rfc2732.txt


Clicking on this internal hyperlink will take us to the target_ below.

.. _target:

The hyperlink target above points to this paragraph.

Source code examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is an example::

    from django.http import HttpResponse

	def index(request):
    	return HttpResponse("Hello, world. You're at the poll index.")

Or another example follows below, indented with spaces.

::

  Whitespace, newlines, blank lines, and
  all kinds of markup (like *this* or
  \this) is preserved by literal blocks.

  The paragraph containing only '::'
  will be omitted from the result.

And another type of code inclusion, indented with tabs: ::

	print "More source code"
	print("I love source code")

Some source code that is included:

.. code-block:: s

	lm_difference <- function(groupA, groupB)
	{
	    # Build a linear model with groupA = 0, and groupB = 1

	    y.A <- groupA[!is.na(groupA)]
	    y.B <- groupB[!is.na(groupB)]
		x.A <- numeric(length(y.A))
		x.B <- numeric(length(y.B)) + 1
		y <- c(y.A, y.B)
		x <- c(x.A, x.B)
		x <- factor(x, levels=c("0", "1"), labels=c("A", "B"))

		model <- lm(y ~ x)
	return(list(summary(model), confint(model)))
	}

	brittle <- read.csv('http://stats4.eng.mcmaster.ca/datasets/brittleness-index.csv')
	attach(brittle)

	group_difference(TK104, TK105)  # See Q4 in assignment 3 for this function
	lm_difference(TK104, TK105)

A ``literal-include`` for source code:

.. literalinclude:: my_source_code.py


Lists
======

An unordered list; no spacing between entries; indented with tabs:

	*	A point.
	*	Next point.
	*	Some other point.

Another unordered list; no spacing between entries; flush with margin:

*	Additional point.
*	Further point.
*	Final point.

Another unordered list; with spacing between entries; flush with margin:

*	Some other point.

*	More, and more, points.

*	Hopefully, the final point.

 
Enumerated lists:

3. This is the first item
4. This is the second item
5. Enumerators are arabic numbers,
   single letters, or roman numerals
6. List items should be sequentially
   numbered, but need not start at 1
   (although not all formatters will
   honour the first index).
#. This item is auto-enumerated 

Other enumerated lists examples.

1. Item 1 initial text.

   a) Item here.
   b) And other item here.	

Paragraph of text here.

what
  Definition lists associate a term with
  a definition.

how
  The term is a one-line phrase, and the
  definition is one or more paragraphs or
  body elements, indented relative to the
  term. Blank lines are not allowed
  between term and definition.

An unordered list; no spacing between entries; indented with tabs, then spaces after the tabs:

	* A point.
	* Next point.
	* Some other point.

Another unordered list; no spacing between entries; flush with margin, only spaces after the bullet:

* Additional point.
* Further point.
* Final point.

Another source code check
==========================

.. literalinclude:: longer_source_code.py
	:language: python
	:linenos: 
	:start-after: 3
	:lines: 5-16



