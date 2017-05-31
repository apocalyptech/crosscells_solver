Brute-Force Solver for CrossCells
=================================

CrossCells is the latest (as of May 31, 2017) puzzle game from Matthew Brown
(HexCells, SquareCells) - http://store.steampowered.com/app/632000/CrossCells/

This is a brute-force solver for CrossCells levels, written in Python.  It
actually will run under PyPy3 by default, so you'll need to install that.
Python itself can be used instead, but PyPy3 provides some pretty extreme
performance improvements, and allows for a few levels to be solved in a matter
of minutes rather than hours.

There's nothing clever about what this does, and a few of the puzzles (namely
puzzles 43, 47, and 49) have prohibitively-large possibilities which preclude
using this utility on them (though level 43 could be solved in about half a
year if you wanted to dedicate a core to the process for that long).  I'm
afraid I'm not really interested enough to write a "real" solver, using logic
instead of brute-force methods, to address this gap.

Tested on PyPy3, as I mentioned.  I don't think there's anything in here which
would not work on Python 2, but it's completely untested there.

The util chooses between two brute-force methods after reading the level data,
based on some benchmarks.  Browse the code for some details on that.  The
time estimates are just hardcoded in the file and are obviously only going to
be accurate if you're running the same CPU as me.  I'd expect that the relative
ratio of processing time between the two methods is probably the same regardless
of CPU, so I'd hope it would at least pick the "best" method to use, even if
the time estimates are off.
