A section of various tables
==========================================================

There are variety of ways to specify a table.

.. tabularcolumns:: |l|lllllllll|

.. table::

    ==========   === === === === === === === === ===
    **Case A**   254 440 501 368 697 476 188 525
    ----------   --- --- --- --- --- --- --- --- ---
    **Case B**   338 470 558 426 733 539 240 628 517
    ==========   === === === === === === === === ===

An indented grid table:

    .. table::

        +------------+------------+-----------+
        | Header 1   | Header 2   | Header 3  |
        +============+============+===========+
        | body row 1 | column 2   | column 3  |
        +------------+------------+-----------+

.. We cannot handle these yet with the text-based builder
.. | body row 2 | Cells may span columns.|
.. +------------+------------+-----------+
.. | body row 3 | Cells may  | - Cells   |
.. +------------+ span rows. | - contain |
.. | body row 4 |            | - blocks. |
.. +------------+------------+-----------+

Or a simple table, this time with a caption

.. table:: Simple table caption

    =====  =====  ======
    Input  Input  Output
    -----  -----  ------
    A      B      A or B
    =====  =====  ======
    False  False  False
    True   False  True
    False  True   True
    True   True   True
    =====  =====  ======